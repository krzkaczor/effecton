"""HttpClient service: Protocol plus SyncLive, AsyncLive and a canned Test.

Requests and responses are plain values (Request, Response), and this
module is the only place that talks to the network. SyncLive sends each
request through a blocking httpx2.Client, so it suits run_sync; AsyncLive
sends it through httpx2.AsyncClient, so the loop keeps turning under
run_async and run_main. Both share one error mapping: the transport failing
(a connection that could not be made or was lost, a proxy refusing, a
reply that was not HTTP) is the one typed error, TransportError, as in
Effect-TS; everything else stays a defect, including a URL without a
scheme, which is a programming error. Test answers from a canned
url -> body mapping or from a handler and records every request, so a
program sees the same Exit whichever implementation it runs against.

Status semantics follow Effect-TS's HttpClient: every status comes back as
a Response, and filter_status_ok is the opt-in that turns a non-2xx into a
StatusError. Redirects are not followed and the clients set no HTTP-level
timeout, so a slow server is bounded the effecton way, by composing
effect.timeout(...). Naming follows Effect-TS with these deliberate
differences: delete is spelled out (del is a Python keyword), and
Response.json() is an effect that fails with InvalidJson.
"""

import codecs
import typing
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from json import dumps, loads
from typing import Any, Literal, final, runtime_checkable
from urllib.parse import urlencode

import httpx2

from effecton.attempt import attempt, attempt_async
from effecton.effect import Effect, EffectonError, fail, success
from effecton.suspend import suspend

type Method = Literal["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


@final
@dataclass(frozen=True)
class TransportError(EffectonError):
    """The request never got a valid response: the connection could not be
    made or was lost, a proxy refused, or the reply was not HTTP."""

    method: Method
    url: str
    message: str

    def __str__(self) -> str:
        return f"{self.method} {self.url} failed: {self.message}"


@final
@dataclass(frozen=True)
class StatusError(EffectonError):
    method: Method
    url: str
    status: int

    def __str__(self) -> str:
        return f"{self.method} {self.url} returned HTTP {self.status}"


@final
@dataclass(frozen=True)
class InvalidJson(EffectonError):
    method: Method
    url: str
    message: str

    def __str__(self) -> str:
        return (
            f"{self.method} {self.url} returned a body that is not JSON: {self.message}"
        )


type HttpClientError = TransportError | StatusError | InvalidJson


@final
@dataclass(frozen=True)
class Request:
    """What gets sent: the conveniences on Protocol build one, execute takes it."""

    method: Method
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None


@final
@dataclass(frozen=True)
class Response:
    """A fully read response. Header names are lowercase and a header that
    was sent more than once is comma-joined, as httpx reports them."""

    request: Request
    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""

    @property
    def is_success(self) -> bool:
        return 200 <= self.status < 300

    @property
    def text(self) -> str:
        """The body decoded with the content-type charset, utf-8 when there is
        none or it is unknown; undecodable bytes become U+FFFD, as in httpx."""
        return self.body.decode(_charset(self.headers), errors="replace")

    def json(self) -> Effect[Any, InvalidJson]:
        def to_error(e: Exception) -> InvalidJson:
            # JSONDecodeError and UnicodeDecodeError are both ValueErrors.
            if isinstance(e, ValueError):
                return InvalidJson(
                    method=self.request.method, url=self.request.url, message=str(e)
                )
            raise e

        return attempt(lambda: loads(self.body), to_error)


@runtime_checkable
class Protocol(typing.Protocol):
    def execute(self, request: Request) -> Effect[Response, TransportError]:
        """Send the request and read the whole response, whatever its status."""
        ...

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
    ) -> Effect[Response, TransportError]:
        """params are url-encoded onto the query string."""
        return self.execute(_request("GET", url, headers=headers, params=params))

    def head(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
    ) -> Effect[Response, TransportError]:
        return self.execute(_request("HEAD", url, headers=headers, params=params))

    def options(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
    ) -> Effect[Response, TransportError]:
        return self.execute(_request("OPTIONS", url, headers=headers, params=params))

    def delete(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
    ) -> Effect[Response, TransportError]:
        return self.execute(_request("DELETE", url, headers=headers, params=params))

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        body: bytes | str | None = None,
        json: object = None,
    ) -> Effect[Response, TransportError]:
        """A str body is utf-8 encoded; json is serialized and sets
        content-type: application/json unless a content-type header is given.
        Giving both body and json is a ValueError."""
        return self.execute(
            _request("POST", url, headers=headers, params=params, body=body, json=json)
        )

    def put(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        body: bytes | str | None = None,
        json: object = None,
    ) -> Effect[Response, TransportError]:
        return self.execute(
            _request("PUT", url, headers=headers, params=params, body=body, json=json)
        )

    def patch(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        body: bytes | str | None = None,
        json: object = None,
    ) -> Effect[Response, TransportError]:
        return self.execute(
            _request("PATCH", url, headers=headers, params=params, body=body, json=json)
        )


def filter_status_ok(response: Response) -> Effect[Response, StatusError]:
    """The response when its status is 2xx, otherwise a StatusError; Effect-TS's
    filterStatusOk applied per response: http.get(url).flat_map(filter_status_ok)."""
    if response.is_success:
        return success(response)
    return fail(
        StatusError(
            method=response.request.method,
            url=response.request.url,
            status=response.status,
        )
    )


@final
@dataclass(frozen=True)
class SyncLive(Protocol):
    """The real network through a blocking httpx2.Client; suits run_sync.

    A fresh client is opened per request (no connection pooling yet) with no
    HTTP-level timeout, so a request is bounded by composing
    effect.timeout(...), which needs an async runner.
    """

    def execute(self, request: Request) -> Effect[Response, TransportError]:
        def go() -> Response:
            with httpx2.Client(timeout=None) as client:
                raw = client.request(
                    request.method,
                    request.url,
                    headers=request.headers,
                    content=request.body,
                )
            return _response(request, raw)

        return attempt(go, _transport_error(request))


@final
@dataclass(frozen=True)
class AsyncLive(Protocol):
    """The real network through httpx2.AsyncClient; suits run_async and run_main.

    Each request opens a fresh client with no HTTP-level timeout, so
    effect.timeout(...) is how a request gets bounded, and a cancellation
    aborts the request. Under run_sync the effects die with
    AsyncEffectInSyncRun, like any coroutine effect.
    """

    def execute(self, request: Request) -> Effect[Response, TransportError]:
        async def go() -> Response:
            async with httpx2.AsyncClient(timeout=None) as client:
                raw = await client.request(
                    request.method,
                    request.url,
                    headers=request.headers,
                    content=request.body,
                )
            return _response(request, raw)

        return attempt_async(go, _transport_error(request))


type Handler = Callable[[Request], Response | TransportError]


@final
@dataclass
class Test(Protocol):
    """A client that never touches the network.

    Seed it with responses, a url -> body mapping answered with a 200 (a str
    body is utf-8 encoded) where any other url gets an empty 404; or give a
    handler that receives the normalized Request and returns the Response,
    or a TransportError to fail with. Either way every executed request is
    appended to requests, in order, so a test can assert on what was sent.
    """

    responses: Mapping[str, str | bytes] = field(default_factory=dict)
    handler: Handler | None = None
    requests: list[Request] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.handler is not None and self.responses:
            raise ValueError("Give either responses or a handler, not both")

    @suspend
    def execute(self, request: Request) -> Effect[Response, TransportError]:
        self.requests.append(request)
        if self.handler is not None:
            answer = self.handler(request)
            return success(answer) if isinstance(answer, Response) else fail(answer)
        body = self.responses.get(request.url)
        if body is None:
            return success(Response(request=request, status=404))
        content = body.encode() if isinstance(body, str) else body
        return success(Response(request=request, status=200, body=content))


def _request(
    method: Method,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, str] | None = None,
    body: bytes | str | None = None,
    json: object = None,
) -> Request:
    if body is not None and json is not None:
        raise ValueError("Give either body or json, not both")
    merged = dict(headers or {})
    if params:
        url = f"{url}{'&' if '?' in url else '?'}{urlencode(params)}"
    content: bytes | None
    if json is not None:
        content = dumps(json).encode()
        if not any(name.lower() == "content-type" for name in merged):
            merged["content-type"] = "application/json"
    elif isinstance(body, str):
        content = body.encode()
    else:
        content = body
    return Request(method, url, merged, content)


def _response(request: Request, raw: httpx2.Response) -> Response:
    return Response(
        request=request,
        status=raw.status_code,
        headers=dict(raw.headers.items()),
        body=raw.content,
    )


def _transport_error(request: Request) -> Callable[[Exception], TransportError]:
    def to_error(e: Exception) -> TransportError:
        # A URL without a scheme is a programming error and LocalProtocolError a
        # bug in the client, so neither is typed.
        if isinstance(e, httpx2.UnsupportedProtocol | httpx2.LocalProtocolError):
            raise e
        if isinstance(e, httpx2.TransportError | httpx2.DecodingError):
            return TransportError(
                method=request.method, url=request.url, message=str(e)
            )
        raise e

    return to_error


def _charset(headers: Mapping[str, str]) -> str:
    for name, value in headers.items():
        if name.lower() != "content-type":
            continue
        for parameter in value.split(";")[1:]:
            key, _, charset = parameter.strip().partition("=")
            if key.strip().lower() == "charset":
                try:
                    return codecs.lookup(charset.strip().strip('"')).name
                except LookupError:
                    return "utf-8"
    return "utf-8"
