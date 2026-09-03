from pathlib import Path

import effecton as E
from changesets.shared import pyproject_version
from changesets.shared.pyproject_version import AmbiguousVersionLine, MissingVersionLine

PATH = Path("/repo/packages/effecton/pyproject.toml")
TEXT = '[project]\nname = "effecton"\nversion = "0.1.0"\ndescription = "x"\n'


def test_reads_the_version():
    result = E.run_sync(pyproject_version.read_version(PATH, TEXT))

    assert result == E.Succeeded(value="0.1.0")


def test_replaces_only_the_version_line():
    result = E.run_sync(pyproject_version.replace_version(PATH, TEXT, "0.2.0"))

    assert result == E.Succeeded(
        value='[project]\nname = "effecton"\nversion = "0.2.0"\ndescription = "x"\n'
    )


def test_fails_when_no_version_line_exists():
    text = '[project]\nname = "effecton"\n'

    result = E.run_sync(pyproject_version.read_version(PATH, text))

    assert result == E.Failure(cause=E.Fail(MissingVersionLine(path=PATH)))


def test_fails_when_more_than_one_version_line_exists():
    text = 'version = "0.1.0"\n[tool.x]\nversion = "9.9.9"\n'

    result = E.run_sync(pyproject_version.read_version(PATH, text))

    assert result == E.Failure(cause=E.Fail(AmbiguousVersionLine(path=PATH)))


def test_indented_or_inline_version_keys_do_not_count():
    text = '[project]\nversion = "0.1.0"\ndependencies = ["pkg>=1", "version "]\n'

    result = E.run_sync(pyproject_version.read_version(PATH, text))

    assert result == E.Succeeded(value="0.1.0")
