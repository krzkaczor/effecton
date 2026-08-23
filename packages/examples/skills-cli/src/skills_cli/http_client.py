"""HTTP service: Protocol plus Live (httpx) and Test (canned responses)."""

import typing
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import runtime_checkable

import httpx

import effecton as E
from skills_cli.errors import HttpError, HttpRequestError, HttpStatusError


@runtime_checkable
class Protocol(typing.Protocol):
    def get_text(self, url: str) -> E.Effect[str, HttpError]: ...


@dataclass(frozen=True)
class Live(Protocol):
    client: httpx.Client = field(default_factory=httpx.Client)

    def get_text(self, url: str) -> E.Effect[str, HttpError]:
        def go() -> str:
            response = self.client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text

        def to_error(e: Exception) -> HttpError:
            if isinstance(e, httpx.HTTPStatusError):
                return HttpStatusError(url=url, status_code=e.response.status_code)
            if isinstance(e, httpx.RequestError):
                return HttpRequestError(url=url, message=str(e))
            raise e

        return E.attempt(go, to_error)


@dataclass(frozen=True)
class Test(Protocol):
    __test__ = False

    responses: Mapping[str, str] = field(default_factory=dict)

    def get_text(self, url: str) -> E.Effect[str, HttpError]:
        if url not in self.responses:
            return E.fail(HttpStatusError(url=url, status_code=404))
        return E.success(self.responses[url])
