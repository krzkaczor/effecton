import httpx

import effecton as E
from skills_cli import http_client as HttpClient

URL = "https://raw.githubusercontent.com/octo/my-skill/main/SKILL.md"


def test_live_returns_the_response_body():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="body"))
    http = HttpClient.Live(client=httpx.Client(transport=transport))

    result = E.run_sync(http.get_text(URL))

    assert result == E.Succeeded(value="body")


def test_live_fails_on_an_error_status():
    transport = httpx.MockTransport(lambda request: httpx.Response(404))
    http = HttpClient.Live(client=httpx.Client(transport=transport))

    result = E.run_sync(http.get_text(URL))

    assert result == E.Failure(
        cause=E.Fail(HttpClient.HttpStatusError(url=URL, status_code=404))
    )


def test_live_fails_on_a_transport_error():
    def raise_connect_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    transport = httpx.MockTransport(raise_connect_error)
    http = HttpClient.Live(client=httpx.Client(transport=transport))

    result = E.run_sync(http.get_text(URL))

    assert result == E.Failure(
        cause=E.Fail(HttpClient.HttpRequestError(url=URL, message="connection refused"))
    )


def test_test_impl_serves_canned_responses():
    http = HttpClient.Test(responses={URL: "body"})

    assert E.run_sync(http.get_text(URL)) == E.Succeeded(value="body")


def test_test_impl_fails_with_404_on_a_miss():
    http = HttpClient.Test()

    result = E.run_sync(http.get_text(URL))

    assert result == E.Failure(
        cause=E.Fail(HttpClient.HttpStatusError(url=URL, status_code=404))
    )
