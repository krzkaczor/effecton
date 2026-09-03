from pathlib import Path

import effecton as E
from changesets.shared import file_system as FileSystem
from changesets.shared import git as Git
from changesets.shared.config import UnknownPackage
from changesets.shared.github import NotAGitHubRemote
from changesets.shared.pyproject_version import MissingVersionLine
from changesets.shared.release_plan import Release
from changesets.shared.semver import Version
from changesets.version.program import apply_versions

ROOT = Path("/repo")
CS_DIR = ROOT / ".changeset"
CONFIG = CS_DIR / "config.toml"
CONFIG_TEXT = '[packages]\neffecton = "packages/effecton"\n'
PYPROJECT = ROOT / "packages/effecton/pyproject.toml"
PYPROJECT_TEXT = '[project]\nname = "effecton"\nversion = "0.1.0"\n'
CHANGELOG = ROOT / "packages/effecton/CHANGELOG.md"
ORIGIN = "git@github.com:krzkaczor/effecton.git"
PR = "https://github.com/krzkaczor/effecton/pull"


def make_fs(extra_files=None):
    files = {CONFIG: CONFIG_TEXT, PYPROJECT: PYPROJECT_TEXT, **(extra_files or {})}
    return FileSystem.Test(files=files, dirs={CS_DIR})


def make_git(subjects=None, origin=ORIGIN):
    remotes = {} if origin is None else {"origin": origin}
    return Git.Test(subjects=subjects or {}, remotes=remotes)


def wire(fs, git=None):
    entries: list[E.LogData] = []
    loggers = E.CurrentLoggers((E.EffectonLogger(log=entries.append),))
    provided = (
        apply_versions(ROOT)
        .provide(FileSystem.Protocol)(fs)
        .provide(Git.Protocol)(git or make_git())
    )
    return E.provide_implicit(provided, loggers)


def test_no_changesets_is_a_no_op():
    fs = make_fs()

    result = E.run_sync(wire(fs, make_git(origin=None)))

    assert result == E.Succeeded(value=())
    assert fs.files == {CONFIG: CONFIG_TEXT, PYPROJECT: PYPROJECT_TEXT}


def test_applies_changesets_bumping_by_the_strongest_level():
    fs = make_fs(
        extra_files={
            CS_DIR / "one.md": "---\neffecton: minor\n---\n\nAdd retry.\n",
            CS_DIR / "two.md": "---\neffecton: patch\n---\n\nFix a bug.\n",
        }
    )
    git = make_git(
        subjects={
            CS_DIR / "one.md": "Add retry (#4)",
            CS_DIR / "two.md": "Merge pull request #5 from krzkaczor/fix",
        }
    )

    result = E.run_sync(wire(fs, git))

    assert result == E.Succeeded(
        value=(
            Release(
                package="effecton",
                old=Version(major=0, minor=1, patch=0),
                new=Version(major=0, minor=2, patch=0),
            ),
        )
    )
    assert fs.files[PYPROJECT] == '[project]\nname = "effecton"\nversion = "0.2.0"\n'
    assert fs.files[CHANGELOG] == (
        "# effecton\n\n"
        "## 0.2.0\n\n"
        "### Minor Changes\n\n"
        f"- Add retry. ([#4]({PR}/4))\n\n"
        "### Patch Changes\n\n"
        f"- Fix a bug. ([#5]({PR}/5))\n"
    )
    assert CS_DIR / "one.md" not in fs.files
    assert CS_DIR / "two.md" not in fs.files


def test_a_changeset_without_a_pull_request_is_rendered_unlinked():
    fs = make_fs(
        extra_files={CS_DIR / "one.md": "---\neffecton: patch\n---\n\nFix a bug.\n"}
    )
    git = make_git(subjects={CS_DIR / "one.md": "Fix a bug"})

    result = E.run_sync(wire(fs, git))

    assert isinstance(result, E.Succeeded)
    assert fs.files[CHANGELOG] == (
        "# effecton\n\n## 0.1.1\n\n### Patch Changes\n\n- Fix a bug.\n"
    )


def test_a_major_changeset_bumps_to_the_next_major():
    fs = make_fs(
        extra_files={CS_DIR / "one.md": "---\neffecton: major\n---\n\nBreak it.\n"}
    )

    result = E.run_sync(wire(fs))

    assert result == E.Succeeded(
        value=(
            Release(
                package="effecton",
                old=Version(major=0, minor=1, patch=0),
                new=Version(major=1, minor=0, patch=0),
            ),
        )
    )


def test_prepends_to_an_existing_changelog():
    existing = "# effecton\n\n## 0.1.0\n\n### Minor Changes\n\n- First release.\n"
    fs = make_fs(
        extra_files={
            CHANGELOG: existing,
            CS_DIR / "one.md": "---\neffecton: patch\n---\n\nFix a bug.\n",
        }
    )
    git = make_git(subjects={CS_DIR / "one.md": "Fix a bug (#6)"})

    result = E.run_sync(wire(fs, git))

    assert result == E.Succeeded(
        value=(
            Release(
                package="effecton",
                old=Version(major=0, minor=1, patch=0),
                new=Version(major=0, minor=1, patch=1),
            ),
        )
    )
    assert fs.files[CHANGELOG] == (
        "# effecton\n\n"
        "## 0.1.1\n\n"
        "### Patch Changes\n\n"
        f"- Fix a bug. ([#6]({PR}/6))\n\n"
        "## 0.1.0\n\n"
        "### Minor Changes\n\n"
        "- First release.\n"
    )


def test_a_changeset_for_an_unknown_package_fails_before_writing():
    changeset_path = CS_DIR / "one.md"
    changeset_text = "---\nother: minor\n---\n\nNot ours.\n"
    fs = make_fs(extra_files={changeset_path: changeset_text})

    result = E.run_sync(wire(fs))

    assert result == E.Failure(
        cause=E.Fail(UnknownPackage(path=changeset_path, package="other"))
    )
    assert fs.files == {
        CONFIG: CONFIG_TEXT,
        PYPROJECT: PYPROJECT_TEXT,
        changeset_path: changeset_text,
    }


def test_a_non_github_origin_fails_before_writing():
    changeset_path = CS_DIR / "one.md"
    changeset_text = "---\neffecton: patch\n---\n\nFix a bug.\n"
    fs = make_fs(extra_files={changeset_path: changeset_text})
    origin = "git@gitlab.com:krzkaczor/effecton.git"

    result = E.run_sync(wire(fs, make_git(origin=origin)))

    assert result == E.Failure(cause=E.Fail(NotAGitHubRemote(url=origin)))
    assert fs.files == {
        CONFIG: CONFIG_TEXT,
        PYPROJECT: PYPROJECT_TEXT,
        changeset_path: changeset_text,
    }


def test_a_missing_version_line_fails_before_writing():
    changeset_path = CS_DIR / "one.md"
    changeset_text = "---\neffecton: patch\n---\n\nFix a bug.\n"
    broken_pyproject = '[project]\nname = "effecton"\n'
    fs = make_fs(
        extra_files={changeset_path: changeset_text, PYPROJECT: broken_pyproject}
    )

    result = E.run_sync(wire(fs))

    assert result == E.Failure(cause=E.Fail(MissingVersionLine(path=PYPROJECT)))
    assert fs.files == {
        CONFIG: CONFIG_TEXT,
        PYPROJECT: broken_pyproject,
        changeset_path: changeset_text,
    }
