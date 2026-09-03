import pytest

import effecton as E
from changesets.shared import github
from changesets.shared.github import NotAGitHubRemote, PullRequest


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:krzkaczor/effecton.git",
        "git@github.com:krzkaczor/effecton",
        "ssh://git@github.com/krzkaczor/effecton.git",
        "https://github.com/krzkaczor/effecton.git",
        "https://github.com/krzkaczor/effecton",
        "https://github.com/krzkaczor/effecton/",
    ],
)
def test_parse_repository_accepts_github_remote_forms(url):
    result = E.run_sync(github.parse_repository(url))

    assert result == E.Succeeded(value="krzkaczor/effecton")


@pytest.mark.parametrize(
    "url",
    [
        "git@gitlab.com:krzkaczor/effecton.git",
        "https://github.com/krzkaczor",
        "/srv/git/effecton.git",
    ],
)
def test_parse_repository_rejects_non_github_remotes(url):
    result = E.run_sync(github.parse_repository(url))

    assert result == E.Failure(cause=E.Fail(NotAGitHubRemote(url=url)))


@pytest.mark.parametrize(
    ("subject", "number"),
    [
        ("Add missing changeset for mymy -> ty migration (#4)", 4),
        ("Merge pull request #12 from krzkaczor/feature", 12),
        ("Fix #12 crash", None),
        ("Version Packages", None),
    ],
)
def test_pull_request_number(subject, number):
    assert github.pull_request_number(subject) == number


def test_pull_request_url():
    pr = PullRequest(repository="krzkaczor/effecton", number=4)

    assert pr.url == "https://github.com/krzkaczor/effecton/pull/4"
