from pathlib import Path

import effecton as E
from changesets.add import name_generator as NameGenerator
from changesets.add.program import add_changeset, pick_name
from changesets.shared import file_system as FileSystem
from changesets.shared.config import UnknownPackage

ROOT = Path("/repo")
CS_DIR = ROOT / ".changeset"
CONFIG = CS_DIR / "config.toml"
CONFIG_TEXT = '[packages]\neffecton = "packages/effecton"\n'


def make_fs(extra_files=None):
    files = {CONFIG: CONFIG_TEXT, **(extra_files or {})}
    return FileSystem.Test(files=files, dirs={CS_DIR})


def wire_add(
    fs, name_generator, package="effecton", bump="patch", summary="Fix a bug."
):
    return (
        add_changeset(ROOT, package, bump, summary)
        .provide(FileSystem.Protocol)(fs)
        .provide(NameGenerator.Protocol)(name_generator)
    )


def wire_pick_name(fs, name_generator):
    return (
        pick_name(CS_DIR)
        .provide(FileSystem.Protocol)(fs)
        .provide(NameGenerator.Protocol)(name_generator)
    )


def test_creates_a_changeset():
    fs = make_fs()
    name_generator = NameGenerator.Test(names=["happy-pandas-dance"])

    result = E.run_sync(
        wire_add(fs, name_generator, bump="minor", summary="Add retry.")
    )

    path = CS_DIR / "happy-pandas-dance.md"
    assert result == E.Succeeded(value=path)
    assert fs.files[path] == "---\neffecton: minor\n---\n\nAdd retry.\n"


def test_strips_the_summary():
    fs = make_fs()
    name_generator = NameGenerator.Test()

    result = E.run_sync(wire_add(fs, name_generator, summary="  Fix a bug.\n"))

    path = CS_DIR / "happy-pandas-dance.md"
    assert result == E.Succeeded(value=path)
    assert fs.files[path] == "---\neffecton: patch\n---\n\nFix a bug.\n"


def test_an_unknown_package_fails():
    fs = make_fs()

    result = E.run_sync(wire_add(fs, NameGenerator.Test(), package="nope"))

    assert result == E.Failure(
        cause=E.Fail(UnknownPackage(path=CONFIG, package="nope"))
    )
    assert set(fs.files) == {CONFIG}


def test_pick_name_returns_the_first_free_name():
    fs = make_fs()
    name_generator = NameGenerator.Test(names=["happy-pandas-dance"])

    result = E.run_sync(wire_pick_name(fs, name_generator))

    assert result == E.Succeeded(value="happy-pandas-dance")


def test_pick_name_skips_taken_names():
    fs = make_fs(extra_files={CS_DIR / "happy-pandas-dance.md": "existing"})
    name_generator = NameGenerator.Test(
        names=["happy-pandas-dance", "quiet-otters-swim"]
    )

    result = E.run_sync(wire_pick_name(fs, name_generator))

    assert result == E.Succeeded(value="quiet-otters-swim")


def test_pick_name_falls_back_to_a_numeric_suffix_after_five_collisions():
    fs = make_fs(extra_files={CS_DIR / "dup.md": "existing"})
    name_generator = NameGenerator.Test(names=["dup"] * 6)

    result = E.run_sync(wire_pick_name(fs, name_generator))

    assert result == E.Succeeded(value="dup-2")


def test_pick_name_increments_the_suffix_past_taken_names():
    fs = make_fs(
        extra_files={
            CS_DIR / "dup.md": "existing",
            CS_DIR / "dup-2.md": "existing",
            CS_DIR / "dup-3.md": "existing",
        }
    )
    name_generator = NameGenerator.Test(names=["dup"] * 6)

    result = E.run_sync(wire_pick_name(fs, name_generator))

    assert result == E.Succeeded(value="dup-4")
