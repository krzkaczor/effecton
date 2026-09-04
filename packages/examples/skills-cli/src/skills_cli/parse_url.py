"""Validate a GitHub SKILL.md URL and normalize it to its raw form."""

from dataclasses import dataclass
from typing import final
from urllib.parse import urlparse

import effecton as E

ALLOWED_HOSTS = {"github.com", "www.github.com", "raw.githubusercontent.com"}


@final
@dataclass(frozen=True)
class UnsupportedHost(E.EffectonError):
    url: str
    host: str

    def __str__(self) -> str:
        return f"Unsupported host {self.host!r} in {self.url}"


@final
@dataclass(frozen=True)
class NotASkillFile(E.EffectonError):
    url: str

    def __str__(self) -> str:
        return f"{self.url} doesn't point to a SKILL.md"


@final
@dataclass(frozen=True)
class MalformedSkillPath(E.EffectonError):
    url: str
    reason: str

    def __str__(self) -> str:
        return f"Couldn't parse {self.url}: {self.reason}"


type ParseUrlError = UnsupportedHost | NotASkillFile | MalformedSkillPath


@dataclass(frozen=True)
class ParsedSkillUrl:
    raw_url: str
    skill_name: str


def parse(url: str) -> E.Effect[ParsedSkillUrl, ParseUrlError]:
    def to_parsed(
        raw_url: str, repo: str, rest: list[str]
    ) -> E.Effect[ParsedSkillUrl, ParseUrlError]:
        # rest ends with SKILL.md: at the repo root the skill is named
        # after the repo, otherwise after its containing directory.
        skill_name = repo if len(rest) == 1 else rest[-2]
        return E.success(ParsedSkillUrl(raw_url=raw_url, skill_name=skill_name))

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        return E.fail(UnsupportedHost(url=url, host=host))

    parts = [segment for segment in parsed.path.split("/") if segment]
    if not parts or parts[-1].lower() != "skill.md":
        return E.fail(NotASkillFile(url=url))

    if host == "raw.githubusercontent.com":
        if len(parts) >= 6 and parts[2:4] == ["refs", "heads"]:
            return to_parsed(url, parts[1], parts[5:])
        if len(parts) >= 4:
            return to_parsed(url, parts[1], parts[3:])

        reason = "expected /owner/repo/[refs/heads/]ref/path"
        return E.fail(MalformedSkillPath(url=url, reason=reason))

    if len(parts) < 5 or parts[2] != "blob":
        reason = "expected /owner/repo/blob/ref/path"
        return E.fail(MalformedSkillPath(url=url, reason=reason))
    owner, repo, _, ref, *rest = parts
    raw_path = "/".join(rest)
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{raw_path}"

    return to_parsed(raw_url, repo, rest)
