from pathlib import Path

import effecton as E
from changesets.shared import file_system as FileSystem
from changesets.shared.repo import NotAChangesetRepo
from changesets.status.program import status

ROOT = Path("/repo")
CS_DIR = ROOT / ".changeset"
CONFIG = CS_DIR / "config.toml"
CONFIG_TEXT = '[packages]\neffecton = "packages/effecton"\n'
PYPROJECT = ROOT / "packages/effecton/pyproject.toml"
PYPROJECT_TEXT = '[project]\nname = "effecton"\nversion = "0.1.0"\n'


def make_fs(extra_files=None):
    files = {CONFIG: CONFIG_TEXT, PYPROJECT: PYPROJECT_TEXT, **(extra_files or {})}
    return FileSystem.Test(files=files, dirs={CS_DIR})


def test_reports_no_pending_changesets():
    program = status(ROOT).provide(FileSystem.Protocol)(make_fs())

    result = E.run_sync(program)

    assert result == E.Succeeded(value="No unreleased changesets found.")


def test_reports_planned_releases_and_changesets():
    fs = make_fs(
        extra_files={
            CS_DIR / "one.md": "---\neffecton: minor\n---\n\nAdd retry.\n",
            CS_DIR / "two.md": "---\neffecton: patch\n---\n\nFix a bug.\n",
        }
    )
    program = status(ROOT).provide(FileSystem.Protocol)(fs)

    result = E.run_sync(program)

    assert result == E.Succeeded(
        value=(
            "Planned releases:\n"
            "\n"
            "- effecton: 0.1.0 -> 0.2.0\n"
            "\n"
            "Changesets:\n"
            "\n"
            "- one.md: effecton (minor)\n"
            "- two.md: effecton (patch)"
        )
    )


def test_fails_outside_a_changeset_repo():
    fs = FileSystem.Test()
    program = status(ROOT).provide(FileSystem.Protocol)(fs)

    result = E.run_sync(program)

    assert result == E.Failure(cause=E.Fail(NotAChangesetRepo(start=ROOT)))


def test_finds_the_root_from_a_subdirectory():
    fs = make_fs()
    program = status(ROOT / "packages/effecton").provide(FileSystem.Protocol)(fs)

    result = E.run_sync(program)

    assert result == E.Succeeded(value="No unreleased changesets found.")
