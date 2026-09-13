"""Live scenarios run against SyncLive and AsyncLive through the live fixture,
talking to a loopback http.server started once per module, so both
implementations are pinned to the same Exit for the same story without
touching the network. A raw socket that answers with a non-HTTP line and a
port that was bound and released cover the failure mappings. Test has its
own scenarios, plus the ones it shares with the Lives through the http
fixture."""

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx2
import pytest

import effecton as E

HC = E.HttpClient


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def reply(self):
        length = int(self.headers.get("content-length", 0))
        body = self.rfile.read(length) if length else b""
        headers = [("content-type", "text/plain")]
        status = 200
        route = self.path.split("?")[0]
        if route == "/echo":
            headers = [("content-type", "application/json")]
            content = json.dumps(
                {
                    "method": self.command,
                    "path": self.path,
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": body.decode(),
                }
            ).encode()
        elif route.startswith("/status/"):
            status = int(route.removeprefix("/status/"))
            content = b""
        elif route == "/latin1":
            headers = [("content-type", "text/plain; charset=latin-1")]
            content = "café".encode("latin-1")
        elif route == "/repeated":
            headers = [("x-repeat", "a"), ("x-repeat", "b")]
            content = b""
        else:
            headers = [("content-type", "application/json")]
            content = b"not json"
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("content-length", str(len(content)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    do_GET = do_HEAD = do_OPTIONS = do_DELETE = do_POST = do_PUT = do_PATCH = reply


@pytest.fixture(scope="module")
def server_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def garbage_url():
    listener = socket.create_server(("127.0.0.1", 0))

    def serve():
        while True:
            try:
                connection, _ = listener.accept()
            except OSError:
                return
            with connection:
                connection.recv(65536)
                connection.sendall(b"this is not http\r\n")

    threading.Thread(target=serve, daemon=True).start()
    yield f"http://127.0.0.1:{listener.getsockname()[1]}"
    listener.close()


@pytest.fixture
def closed_url():
    with socket.create_server(("127.0.0.1", 0)) as listener:
        port = listener.getsockname()[1]
    return f"http://127.0.0.1:{port}"


@pytest.fixture(params=["sync", "async"])
def live(request) -> HC.Protocol:
    return HC.SyncLive() if request.param == "sync" else HC.AsyncLive()


def run(http, effect):
    if isinstance(http, HC.AsyncLive):
        return E.run_async_exit(effect)
    return E.run_sync_exit(effect)


def unwrap(http, effect):
    result = run(http, effect)
    assert isinstance(result, E.Succeeded), result
    return result.value


def failed(error):
    return E.Failure(cause=E.Fail(error))


def test_get_echoes_the_request(live, server_url):
    url = f"{server_url}/echo"

    response = unwrap(live, live.get(url))
    echoed = unwrap(live, response.json())

    assert response.status == 200
    assert response.request == HC.Request("GET", url)
    assert echoed["method"] == "GET"
    assert echoed["path"] == "/echo"
    assert echoed["body"] == ""


@pytest.mark.parametrize(
    "method", ["HEAD", "OPTIONS", "DELETE", "POST", "PUT", "PATCH"]
)
def test_every_method_has_a_convenience(live, server_url, method):
    url = f"{server_url}/echo"
    send = getattr(live, method.lower())

    response = unwrap(live, send(url))

    assert response.status == 200
    assert response.request.method == method
    if method == "HEAD":
        assert response.body == b""
    else:
        assert unwrap(live, response.json())["method"] == method


def test_params_are_encoded_onto_the_query_string(live, server_url):
    plain = live.get(f"{server_url}/echo", params={"a": "1", "b": "two words"})
    extended = live.get(f"{server_url}/echo?a=1", params={"b": "2"})

    assert unwrap(live, plain.flat_map(lambda r: r.json()))["path"] == (
        "/echo?a=1&b=two+words"
    )
    assert unwrap(live, extended.flat_map(lambda r: r.json()))["path"] == (
        "/echo?a=1&b=2"
    )


def test_post_json_serializes_and_sets_the_content_type(live, server_url):
    url = f"{server_url}/echo"

    echoed = unwrap(live, live.post(url, json={"n": 1}).flat_map(lambda r: r.json()))

    assert echoed["headers"]["content-type"] == "application/json"
    assert json.loads(echoed["body"]) == {"n": 1}


def test_a_given_content_type_wins_over_the_json_default(live, server_url):
    url = f"{server_url}/echo"
    headers = {"Content-Type": "application/vnd.api+json"}

    echoed = unwrap(
        live,
        live.post(url, headers=headers, json=[1]).flat_map(lambda r: r.json()),
    )

    assert echoed["headers"]["content-type"] == "application/vnd.api+json"


def test_str_and_bytes_bodies_are_sent_as_is(live, server_url):
    url = f"{server_url}/echo"

    as_text = unwrap(live, live.put(url, body="héllo").flat_map(lambda r: r.json()))
    as_bytes = unwrap(
        live, live.patch(url, body="héllo".encode()).flat_map(lambda r: r.json())
    )

    assert as_text["body"] == "héllo"
    assert as_bytes["body"] == "héllo"


def test_response_header_names_are_lowercase_and_repeats_join(live, server_url):
    response = unwrap(live, live.get(f"{server_url}/repeated"))

    assert response.headers["x-repeat"] == "a, b"
    assert "content-length" in response.headers


def test_a_non_2xx_status_is_a_response_not_a_failure(live, server_url):
    response = unwrap(live, live.get(f"{server_url}/status/404"))

    assert response.status == 404
    assert response.is_success is False
    assert response.body == b""


def test_filter_status_ok_passes_2xx_and_fails_the_rest(live, server_url):
    good = live.get(f"{server_url}/status/204").flat_map(HC.filter_status_ok)
    bad = live.get(f"{server_url}/status/500").flat_map(HC.filter_status_ok)

    assert unwrap(live, good).status == 204
    assert run(live, bad) == failed(
        HC.StatusError(method="GET", url=f"{server_url}/status/500", status=500)
    )


def test_text_honours_the_content_type_charset(live, server_url):
    response = unwrap(live, live.get(f"{server_url}/latin1"))

    assert response.text == "café"


def test_json_fails_on_a_body_that_is_not_json(live, server_url):
    url = f"{server_url}/not-json"

    result = run(live, live.get(url).flat_map(lambda r: r.json()))

    match result:
        case E.Failure(cause=E.Fail(HC.InvalidJson(method="GET", url=error_url))):
            assert error_url == url
        case _:
            pytest.fail(f"unexpected exit {result}")


def test_a_refused_connection_is_a_transport_error(live, closed_url):
    result = run(live, live.get(closed_url))

    match result:
        case E.Failure(cause=E.Fail(HC.TransportError(method="GET", url=url))):
            assert url == closed_url
        case _:
            pytest.fail(f"unexpected exit {result}")


def test_a_url_without_a_scheme_is_a_defect(live):
    result = run(live, live.get("example.org/path"))

    match result:
        case E.Failure(cause=E.Die(defect=httpx2.UnsupportedProtocol())):
            pass
        case _:
            pytest.fail(f"unexpected exit {result}")


def test_a_reply_that_is_not_http_is_a_transport_error_too(live, garbage_url):
    result = run(live, live.get(garbage_url))

    match result:
        case E.Failure(cause=E.Fail(HC.TransportError(method="GET", url=url))):
            assert url == garbage_url
        case _:
            pytest.fail(f"unexpected exit {result}")


def test_async_live_dies_under_run_sync():
    result = E.run_sync_exit(HC.AsyncLive().get("http://127.0.0.1:1/"))

    assert result == E.Failure(cause=E.Die(defect=E.AsyncEffectInSyncRun()))


def test_giving_both_body_and_json_is_an_error():
    http = HC.Test()

    with pytest.raises(ValueError, match="either body or json"):
        http.post("https://example.org", body="x", json={"x": 1})


def test_canned_responses_answer_with_200_and_the_body():
    http = HC.Test(
        responses={"https://a.test/text": "héllo", "https://a.test/bin": b"\x00"}
    )

    text = E.run_sync(http.get("https://a.test/text"))
    binary = E.run_sync(http.get("https://a.test/bin"))

    assert (text.status, text.text) == (200, "héllo")
    assert (binary.status, binary.body) == (200, b"\x00")


def test_a_canned_miss_is_a_404():
    http = HC.Test(responses={"https://a.test/known": "body"})
    url = "https://a.test/unknown"

    response = E.run_sync(http.get(url))
    filtered = E.run_sync_exit(http.get(url).flat_map(HC.filter_status_ok))

    assert response == HC.Response(request=HC.Request("GET", url), status=404)
    assert filtered == failed(HC.StatusError(method="GET", url=url, status=404))


def test_every_request_is_recorded_in_order():
    http = HC.Test()

    E.run_sync(http.get("https://a.test/1", params={"q": "x"}))
    E.run_sync(http.post("https://a.test/2", json={"n": 1}))

    assert http.requests == [
        HC.Request("GET", "https://a.test/1?q=x"),
        HC.Request(
            "POST",
            "https://a.test/2",
            headers={"content-type": "application/json"},
            body=b'{"n": 1}',
        ),
    ]


def test_a_handler_sees_the_request_and_picks_the_response():
    def handler(request: HC.Request) -> HC.Response:
        return HC.Response(request, 201, headers={"x-seen": request.method})

    http = HC.Test(handler=handler)

    response = E.run_sync(http.put("https://a.test/thing", body=b"x"))

    assert response.status == 201
    assert response.headers == {"x-seen": "PUT"}
    assert response.request.body == b"x"


def test_a_handler_returning_an_error_fails_the_request():
    url = "https://a.test/down"
    error = HC.TransportError(method="GET", url=url, message="refused")
    http = HC.Test(handler=lambda request: error)

    result = E.run_sync_exit(http.get(url))

    assert result == failed(error)


def test_responses_and_a_handler_are_exclusive():
    with pytest.raises(ValueError, match="either responses or a handler"):
        HC.Test(
            responses={"https://a.test": "x"},
            handler=lambda request: HC.Response(request, 200),
        )


def test_text_falls_back_to_utf8_without_or_with_an_unknown_charset():
    request = HC.Request("GET", "https://a.test")
    bare = HC.Response(request, 200, body="héllo".encode())
    unknown = HC.Response(
        request,
        200,
        headers={"content-type": "text/plain; charset=nope"},
        body="héllo".encode(),
    )
    broken = HC.Response(request, 200, body=b"\xff")

    assert bare.text == "héllo"
    assert unknown.text == "héllo"
    assert broken.text == "�"


def test_json_decodes_the_body_and_rejects_bad_bytes():
    request = HC.Request("GET", "https://a.test")
    good = HC.Response(request, 200, body=b'{"a": [1, 2]}')
    bad = HC.Response(request, 200, body=b"\xff")

    assert E.run_sync(good.json()) == {"a": [1, 2]}
    match E.run_sync_exit(bad.json()):
        case E.Failure(
            cause=E.Fail(HC.InvalidJson(method="GET", url="https://a.test"))
        ):
            pass
        case other:
            pytest.fail(f"unexpected exit {other}")
