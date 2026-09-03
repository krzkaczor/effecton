from pathlib import Path

import effecton as E
from changesets.shared import changeset
from changesets.shared.changeset import Changeset, InvalidBumpLevel, MalformedChangeset
from changesets.shared.config import UnknownPackage

PATH = Path("/repo/.changeset/happy-pandas-dance.md")
KNOWN = ("effecton",)


def test_parses_a_changeset():
    text = "---\neffecton: minor\n---\n\nAdd `E.retry` combinator.\n"

    result = E.run_sync(changeset.parse(PATH, text, KNOWN))

    assert result == E.Succeeded(
        value=Changeset(
            path=PATH,
            bumps={"effecton": "minor"},
            summary="Add `E.retry` combinator.",
        )
    )


def test_rejects_an_empty_frontmatter():
    result = E.run_sync(changeset.parse(PATH, "no frontmatter at all", KNOWN))

    assert result == E.Failure(
        cause=E.Fail(
            MalformedChangeset(path=PATH, reason="frontmatter lists no packages")
        )
    )


def test_rejects_an_unknown_package():
    text = "---\nother: minor\n---\n\nsummary\n"

    result = E.run_sync(changeset.parse(PATH, text, KNOWN))

    assert result == E.Failure(cause=E.Fail(UnknownPackage(path=PATH, package="other")))


def test_rejects_an_invalid_bump_level():
    text = "---\neffecton: huge\n---\n\nsummary\n"

    result = E.run_sync(changeset.parse(PATH, text, KNOWN))

    assert result == E.Failure(cause=E.Fail(InvalidBumpLevel(path=PATH, value="huge")))


def test_rejects_unparseable_yaml():
    text = "---\n{ not: valid: yaml\n---\n\nsummary\n"

    result = E.run_sync(changeset.parse(PATH, text, KNOWN))

    assert isinstance(result, E.Failure)
    assert isinstance(result.cause, E.Fail)
    assert isinstance(result.cause.error, MalformedChangeset)


def test_serializes_the_parseable_format():
    text = changeset.serialize({"effecton": "patch"}, "Fix a bug.")

    result = E.run_sync(changeset.parse(PATH, text, KNOWN))

    assert text == "---\neffecton: patch\n---\n\nFix a bug.\n"
    assert result == E.Succeeded(
        value=Changeset(path=PATH, bumps={"effecton": "patch"}, summary="Fix a bug.")
    )
