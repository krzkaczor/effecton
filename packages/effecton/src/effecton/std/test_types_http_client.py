"""Type-level pins for the HttpClient service. Nothing here runs: ty checks
the function bodies and pytest never calls them, so nothing touches the network."""

from datetime import timedelta
from typing import Any, Never, assert_type

import effecton as E

HC = E.HttpClient


def _every_op_carries_its_own_error_union() -> None:
    http: HC.Protocol = HC.SyncLive()
    url = "https://example.org"
    request = HC.Request("GET", url)

    assert_type(http.execute(request), E.Effect[HC.Response, HC.TransportError])
    assert_type(http.get(url), E.Effect[HC.Response, HC.TransportError])
    assert_type(http.head(url), E.Effect[HC.Response, HC.TransportError])
    assert_type(http.options(url), E.Effect[HC.Response, HC.TransportError])
    assert_type(http.delete(url), E.Effect[HC.Response, HC.TransportError])
    assert_type(http.post(url, json={"a": 1}), E.Effect[HC.Response, HC.TransportError])
    assert_type(http.put(url, body=b"x"), E.Effect[HC.Response, HC.TransportError])
    assert_type(http.patch(url, body="x"), E.Effect[HC.Response, HC.TransportError])
    assert_type(
        http.get(url).flat_map(HC.filter_status_ok),
        E.Effect[HC.Response, HC.TransportError | HC.StatusError],
    )
    assert_type(
        http.get(url).timeout(timedelta(seconds=5)),
        E.Effect[HC.Response, HC.TransportError | E.TimeoutException],
    )


def _responses_are_values_with_typed_accessors() -> None:
    response = HC.Response(HC.Request("GET", "https://example.org"), 200)

    assert_type(response.status, int)
    assert_type(response.is_success, bool)
    assert_type(response.text, str)
    assert_type(response.body, bytes)
    assert_type(response.json(), E.Effect[Any, HC.InvalidJson])
    assert_type(HC.filter_status_ok(response), E.Effect[HC.Response, HC.StatusError])


def _the_service_is_an_explicit_requirement() -> None:
    @E.gen
    def fetch() -> E.EffectGen[str, HC.TransportError | HC.StatusError, HC.Protocol]:
        http = yield from E.require(HC.Protocol)

        response = yield from http.get("https://example.org")
        response = yield from HC.filter_status_ok(response)
        return response.text

    assert_type(E.require(HC.Protocol), E.Effect[HC.Protocol, Never, HC.Protocol])
    assert_type(
        fetch().provide(HC.Protocol)(HC.SyncLive()),
        E.Effect[str, HC.TransportError | HC.StatusError],
    )
    assert_type(
        fetch().provide(HC.Protocol)(HC.AsyncLive()),
        E.Effect[str, HC.TransportError | HC.StatusError],
    )
    assert_type(
        fetch().provide(HC.Protocol)(HC.Test()),
        E.Effect[str, HC.TransportError | HC.StatusError],
    )
    assert_type(
        fetch().catch(HC.TransportError)(lambda _: E.success("")),
        E.Effect[str, HC.StatusError, HC.Protocol],
    )

    # The requirement must be provided before running.
    E.run_sync(fetch())  # ty: ignore[invalid-argument-type]


def _test_state_is_typed() -> None:
    canned = HC.Test(responses={"https://example.org": "body"})
    handled = HC.Test(handler=lambda request: HC.Response(request, 200))

    assert_type(canned.requests, list[HC.Request])
    assert_type(handled.handler, HC.Handler | None)


def _http_client_negative() -> None:
    http: HC.Protocol = HC.SyncLive()
    url = "https://example.org"

    # Only an HttpClient implementation can be provided as the HttpClient.
    E.require(HC.Protocol).provide(HC.Protocol)(object())  # ty: ignore[invalid-argument-type]

    # Everything after the url is keyword-only.
    http.get(url, {"accept": "text/plain"})  # ty: ignore[too-many-positional-arguments]

    # Only the seven methods are Methods.
    HC.Request("FETCH", url)  # ty: ignore[invalid-argument-type]

    # A canned body is text or bytes, never a Response.
    HC.Test(responses={url: HC.Response(HC.Request("GET", url), 200)})  # ty: ignore[invalid-argument-type]

    # Implementations are leaves: none can be subclassed.
    class CustomSyncLive(HC.SyncLive):  # ty: ignore[subclass-of-final-class]
        pass

    class CustomAsyncLive(HC.AsyncLive):  # ty: ignore[subclass-of-final-class]
        pass

    class CustomTest(HC.Test):  # ty: ignore[subclass-of-final-class]
        pass
