---
title: HttpClient
description: Sending HTTP requests through the explicit HttpClient requirement, with live clients on httpx2 and a scriptable test client.
---

# HttpClient

`E.HttpClient` talks HTTP. It is an explicit requirement like the FileSystem: a program that needs it says so in `R` through `E.require(E.HttpClient.Protocol)`, and forgetting to provide an implementation is a type error rather than a surprise request. `execute(request)` sends an `E.HttpClient.Request`, and the conveniences build one for you: `get`, `head`, `options` and `delete` take `url, *, headers, params`; `post`, `put` and `patch` add `body` (text or bytes) or `json`, which is serialized and sets the content type. Each returns an `E.HttpClient.Response` with `status`, lowercase `headers`, `body` bytes, a `text` property decoded with the content-type charset and a `json()` effect that fails with `InvalidJson`. As in Effect-TS, every status is a success: `E.HttpClient.filter_status_ok` is the opt-in that turns a non-2xx into `StatusError`. The one request error is `TransportError`, the Transport reason of Effect-TS: the connection could not be made or was lost, or the reply was not HTTP, so `catch(E.HttpClient.TransportError)` handles exactly the network misbehaving. A URL without a scheme is a programming error and stays a defect, as does anything else.

```python
import effecton as E


# ---cut---
@E.gen
def fetch_readme(
    url: str,
) -> E.EffectGen[
    str, E.HttpClient.TransportError | E.HttpClient.StatusError, E.HttpClient.Protocol
]:
    http = yield from E.require(E.HttpClient.Protocol)

    response = yield from http.get(url)
    response = yield from E.HttpClient.filter_status_ok(response)
    return response.text


program = fetch_readme(
    #  ^?
    "https://raw.githubusercontent.com/krzkaczor/effecton/main/README.md"
)
E.run_sync(program.provide(E.HttpClient.Protocol)(E.HttpClient.SyncLive()))
```

There are two live implementations, one per runner, like the Clock: `E.HttpClient.SyncLive` blocks the thread on an [httpx2](https://github.com/pydantic/httpx2) client and suits `run_sync`; `E.HttpClient.AsyncLive` awaits `httpx2.AsyncClient`, so the loop keeps turning under `run_async` and `run_main`. httpx2 is a dependency of effecton, so both are always available. Neither sets an HTTP-level timeout or follows redirects: bound a request the effecton way with `.timeout(...)` (under the async runners), and a 3xx comes back as a `Response`. Each request opens a fresh client for now, so there is no connection pooling yet.

In tests, provide `E.HttpClient.Test`. Seed it with `responses`, a URL-to-body mapping answered with a 200 where any other URL gets a 404, or give it a `handler` that receives the normalized `Request` and returns a `Response` or a request error to fail with. Either way every request is recorded in `requests`:

```python
import effecton as E

URL = "https://raw.githubusercontent.com/krzkaczor/effecton/main/README.md"


@E.gen
def fetch_readme(
    url: str,
) -> E.EffectGen[
    str, E.HttpClient.TransportError | E.HttpClient.StatusError, E.HttpClient.Protocol
]:
    http = yield from E.require(E.HttpClient.Protocol)

    response = yield from http.get(url)
    response = yield from E.HttpClient.filter_status_ok(response)
    return response.text


# ---cut---
def test_fetches_the_readme():
    http = E.HttpClient.Test(responses={URL: "# Effecton"})

    result = E.run_sync(fetch_readme(URL).provide(E.HttpClient.Protocol)(http))

    assert result == "# Effecton"
    assert http.requests == [E.HttpClient.Request("GET", URL)]
```

More examples: [`test_http_client.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_http_client.py). This repo's ruff config bans `httpx`, `httpx2`, `urllib.request` and `http.client` outside the service module, so all requests go through `E.HttpClient`.
