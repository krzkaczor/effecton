from pathlib import Path

import effecton as E
from changesets.notes.program import NoReleasedVersion, latest_notes
from changesets.shared import file_system as FileSystem
from changesets.shared.config import UnknownPackage

ROOT = Path("/repo")
CS_DIR = ROOT / ".changeset"
CONFIG = CS_DIR / "config.toml"
CONFIG_TEXT = '[packages]\neffecton = "packages/effecton"\n'
CHANGELOG = ROOT / "packages/effecton/CHANGELOG.md"


def make_fs(extra_files=None):
    files = {CONFIG: CONFIG_TEXT, **(extra_files or {})}
    return FileSystem.Test(files=files, dirs={CS_DIR})


def wire(fs, package="effecton"):
    return latest_notes(ROOT, package).provide(FileSystem.Protocol)(fs)


def test_returns_the_latest_changelog_section():
    text = "# effecton\n\n## 0.2.0\n\n- New stuff.\n\n## 0.1.0\n\n- Old stuff.\n"
    fs = make_fs(extra_files={CHANGELOG: text})

    result = E.run_sync(wire(fs))

    assert result == E.Succeeded(value="## 0.2.0\n\n- New stuff.\n")


def test_fails_when_the_changelog_is_missing():
    result = E.run_sync(wire(make_fs()))

    assert result == E.Failure(cause=E.Fail(NoReleasedVersion(package="effecton")))


def test_fails_when_the_changelog_has_no_sections():
    fs = make_fs(extra_files={CHANGELOG: "# effecton\n"})

    result = E.run_sync(wire(fs))

    assert result == E.Failure(cause=E.Fail(NoReleasedVersion(package="effecton")))


def test_fails_for_an_unknown_package():
    result = E.run_sync(wire(make_fs(), package="nope"))

    assert result == E.Failure(
        cause=E.Fail(UnknownPackage(path=CONFIG, package="nope"))
    )
