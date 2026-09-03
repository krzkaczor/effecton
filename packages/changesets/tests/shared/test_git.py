import subprocess

import effecton as E
from changesets.shared import git as Git
from changesets.shared.git import GitCommandFailed


def init_repo(path):
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def commit(repo, name, subject):
    (repo / name).write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", name], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "-m",
            subject,
        ],
        check=True,
    )


def test_added_in_returns_the_subject_of_the_adding_commit(tmp_path, monkeypatch):
    init_repo(tmp_path)
    commit(tmp_path, "one.md", "Add thing (#7)")
    commit(tmp_path, "two.md", "Add another (#8)")
    monkeypatch.chdir(tmp_path)

    result = E.run_sync(Git.Live().added_in(tmp_path / "one.md"))

    assert result == E.Succeeded(value="Add thing (#7)")


def test_added_in_is_none_for_an_untracked_path(tmp_path, monkeypatch):
    init_repo(tmp_path)
    commit(tmp_path, "one.md", "Add thing (#7)")
    (tmp_path / "pending.md").write_text("x")
    monkeypatch.chdir(tmp_path)

    result = E.run_sync(Git.Live().added_in(tmp_path / "pending.md"))

    assert result == E.Succeeded(value=None)


def test_remote_url_returns_the_configured_remote(tmp_path, monkeypatch):
    init_repo(tmp_path)
    url = "git@github.com:krzkaczor/effecton.git"
    subprocess.run(
        ["git", "-C", str(tmp_path), "remote", "add", "origin", url], check=True
    )
    monkeypatch.chdir(tmp_path)

    result = E.run_sync(Git.Live().remote_url("origin"))

    assert result == E.Succeeded(value=url)


def test_a_missing_remote_fails(tmp_path, monkeypatch):
    init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = E.run_sync(Git.Live().remote_url("origin"))

    assert isinstance(result, E.Failure)
    assert isinstance(result.cause, E.Fail)
    assert isinstance(result.cause.error, GitCommandFailed)
    assert result.cause.error.command == ("remote", "get-url", "origin")
    assert "origin" in result.cause.error.stderr
