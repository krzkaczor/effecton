"""Every way installing a skill can fail, one frozen dataclass per cause."""

from dataclasses import dataclass
from pathlib import Path

import effecton as E


@dataclass(frozen=True)
class UnsupportedHost(E.EffectonError):
    url: str
    host: str


@dataclass(frozen=True)
class NotASkillFile(E.EffectonError):
    url: str


@dataclass(frozen=True)
class MalformedSkillPath(E.EffectonError):
    url: str
    reason: str


type ParseUrlError = UnsupportedHost | NotASkillFile | MalformedSkillPath


@dataclass(frozen=True)
class HttpRequestError(E.EffectonError):
    url: str
    message: str


@dataclass(frozen=True)
class HttpStatusError(E.EffectonError):
    url: str
    status_code: int


type HttpError = HttpRequestError | HttpStatusError


@dataclass(frozen=True)
class FrontmatterParseError(E.EffectonError):
    message: str


@dataclass(frozen=True)
class PermissionDenied(E.EffectonError):
    path: Path


@dataclass(frozen=True)
class PathIsNotADirectory(E.EffectonError):
    path: Path


@dataclass(frozen=True)
class PathIsADirectory(E.EffectonError):
    path: Path


@dataclass(frozen=True)
class PathAlreadyExists(E.EffectonError):
    path: Path


type FileSystemError = (
    PermissionDenied | PathIsNotADirectory | PathIsADirectory | PathAlreadyExists
)


type InstallError = ParseUrlError | HttpError | FrontmatterParseError | FileSystemError
