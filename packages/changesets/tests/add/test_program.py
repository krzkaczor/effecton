from pathlib import Path

import effecton as E
from changesets.add import name_generator as NameGenerator
from changesets.add.program import add_changeset
from changesets.shared import file_system as FileSystem
from changesets.shared.config import UnknownPackage

ROOT = Path("/repo")
CS_DIR = ROOT / ".changeset"
CONFIG = CS_DIR / "config.toml"
CONFIG_TEXT = '[packages]\neffecton = "packages/effecton"\n'


def make_fs(extra_files=None):
    files = {CONFIG: CONFIG_TEXT, **(extra_files or {})}
    return FileSystem.Test(files=files, dirs={CS_DIR})


def wire(fs, name_generator, package="effecton", bump="patch", summary="Fix a bug."):
    return (
        add_changeset(ROOT, package, bump, summary)
        .provide(FileSystem.Protocol)(fs)
        .provide(NameGenerator.Protocol)(name_generator)
    )


def test_creates_a_changeset():
    fs = make_fs()
    name_generator = NameGenerator.Test(names=["happy-pandas-dance"])

    result = E.run_sync(wire(fs, name_generator, bump="minor", summary="Add retry."))

    path = CS_DIR / "happy-pandas-dance.md"
    assert result == E.Succeeded(value=path)
    assert fs.files[path] == "---\neffecton: minor\n---\n\nAdd retry.\n"


def test_strips_the_summary():
    fs = make_fs()
    name_generator = NameGenerator.Test()

    result = E.run_sync(wire(fs, name_generator, summary="  Fix a bug.\n"))

    path = CS_DIR / "happy-pandas-dance.md"
    assert result == E.Succeeded(value=path)
    assert fs.files[path] == "---\neffecton: patch\n---\n\nFix a bug.\n"


def test_picks_a_fresh_name_when_the_first_is_taken():
    taken = CS_DIR / "happy-pandas-dance.md"
    fs = make_fs(extra_files={taken: "existing"})
    name_generator = NameGenerator.Test(
        names=["happy-pandas-dance", "quiet-otters-swim"]
    )

    result = E.run_sync(wire(fs, name_generator))

    assert result == E.Succeeded(value=CS_DIR / "quiet-otters-swim.md")
    assert fs.files[taken] == "existing"


def test_falls_back_to_a_numeric_suffix_after_five_collisions():
    taken = CS_DIR / "happy-pandas-dance.md"
    fs = make_fs(extra_files={taken: "existing"})
    name_generator = NameGenerator.Test(names=["happy-pandas-dance"] * 6)

    result = E.run_sync(wire(fs, name_generator))

    assert result == E.Succeeded(value=CS_DIR / "happy-pandas-dance-2.md")


def test_an_unknown_package_fails():
    fs = make_fs()

    result = E.run_sync(wire(fs, NameGenerator.Test(), package="nope"))

    assert result == E.Failure(
        cause=E.Fail(UnknownPackage(path=CONFIG, package="nope"))
    )
    assert set(fs.files) == {CONFIG}
