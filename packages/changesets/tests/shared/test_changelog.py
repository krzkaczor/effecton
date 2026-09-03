from pathlib import Path

from changesets.shared import changelog
from changesets.shared.changeset import Changeset
from changesets.shared.semver import Version

VERSION = Version(major=0, minor=2, patch=0)


def cs(name, bumps, summary):
    return Changeset(
        path=Path(f"/repo/.changeset/{name}.md"), bumps=bumps, summary=summary
    )


def test_renders_a_section_grouped_by_bump_level():
    changesets = [
        cs("one", {"effecton": "minor"}, "Add `E.retry`."),
        cs("two", {"effecton": "patch"}, "Fix a bug."),
        cs("three", {"effecton": "minor"}, "Add `E.zip`."),
    ]

    section = changelog.render_section("effecton", VERSION, changesets)

    assert section == (
        "## 0.2.0\n\n"
        "### Minor Changes\n\n"
        "- Add `E.retry`.\n"
        "- Add `E.zip`.\n\n"
        "### Patch Changes\n\n"
        "- Fix a bug.\n"
    )


def test_skips_other_packages_and_empty_summaries():
    changesets = [
        cs("one", {"other": "major"}, "Not ours."),
        cs("two", {"effecton": "patch"}, ""),
        cs("three", {"effecton": "patch"}, "Fix a bug."),
    ]

    section = changelog.render_section("effecton", VERSION, changesets)

    assert section == "## 0.2.0\n\n### Patch Changes\n\n- Fix a bug.\n"


def test_prepend_creates_a_fresh_changelog():
    text = changelog.prepend("effecton", None, "## 0.2.0\n\nsection\n")

    assert text == "# effecton\n\n## 0.2.0\n\nsection\n"


def test_prepend_inserts_after_the_title():
    existing = "# effecton\n\n## 0.1.0\n\nold section\n"

    text = changelog.prepend("effecton", existing, "## 0.2.0\n\nnew section\n")

    assert text == "# effecton\n\n## 0.2.0\n\nnew section\n\n## 0.1.0\n\nold section\n"


def test_prepend_without_a_title_puts_the_section_first():
    existing = "## 0.1.0\n\nold section\n"

    text = changelog.prepend("effecton", existing, "## 0.2.0\n\nnew section\n")

    assert text == "## 0.2.0\n\nnew section\n\n## 0.1.0\n\nold section\n"


def test_latest_section_returns_the_first_release_block():
    text = "# effecton\n\n## 0.2.0\n\nnew section\n\n## 0.1.0\n\nold section\n"

    assert changelog.latest_section(text) == "## 0.2.0\n\nnew section\n"


def test_latest_section_is_none_without_releases():
    assert changelog.latest_section("# effecton\n") is None
