"""Pure GitHub helpers: the remote's `owner/repo` and PR numbers in commits."""

import re
from dataclasses import dataclass

import effecton as E

_REMOTE = re.compile(
    r"^(?:git@github\.com:|ssh://git@github\.com/|https://github\.com/)"
    r"(?P<repository>[^/\s]+/[^/\s]+?)(?:\.git)?/?$"
)
_SQUASH_SUBJECT = re.compile(r"\(#(?P<number>\d+)\)\s*$")
_MERGE_SUBJECT = re.compile(r"^Merge pull request #(?P<number>\d+)\b")


@dataclass(frozen=True)
class NotAGitHubRemote(E.EffectonError):
    url: str

    def __str__(self) -> str:
        return (
            f"Can't link pull requests: remote {self.url!r} is not a GitHub repository"
        )


@dataclass(frozen=True)
class PullRequest:
    repository: str
    number: int

    @property
    def url(self) -> str:
        return f"https://github.com/{self.repository}/pull/{self.number}"


@E.suspend
def parse_repository(url: str) -> E.Effect[str, NotAGitHubRemote]:
    match = _REMOTE.match(url)
    if match is None:
        return E.fail(NotAGitHubRemote(url=url))
    return E.success(match.group("repository"))


def pull_request_number(subject: str) -> int | None:
    """The PR number a squash (`... (#N)`) or merge (`Merge pull request #N`)
    commit subject carries, if any."""
    match = _SQUASH_SUBJECT.search(subject) or _MERGE_SUBJECT.match(subject)
    if match is None:
        return None
    return int(match.group("number"))
