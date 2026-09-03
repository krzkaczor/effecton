"""Render and splice CHANGELOG.md sections, JS-changesets style."""

from collections.abc import Sequence

from changesets.shared.changeset import Changeset
from changesets.shared.semver import BUMPS, Version

_TITLES = {"major": "Major Changes", "minor": "Minor Changes", "patch": "Patch Changes"}


def render_section(
    package: str, version: Version, changesets: Sequence[Changeset]
) -> str:
    parts = [f"## {version}"]
    for level in BUMPS:
        summaries = [
            c.summary for c in changesets if c.bumps.get(package) == level and c.summary
        ]
        if summaries:
            bullets = "\n".join(f"- {summary}" for summary in summaries)
            parts.append(f"### {_TITLES[level]}\n\n{bullets}")

    return "\n\n".join(parts) + "\n"


def prepend(package: str, existing: str | None, section: str) -> str:
    if existing is None or not existing.strip():
        return f"# {package}\n\n{section}"

    head, _, tail = existing.partition("\n")
    if head.startswith("# "):
        rest = tail.lstrip("\n")
        return f"{head}\n\n{section}\n{rest}"
    return f"{section}\n{existing.lstrip()}"


def latest_section(text: str) -> str | None:
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("## ")]
    if not starts:
        return None
    end = starts[1] if len(starts) > 1 else len(lines)

    return "\n".join(lines[starts[0] : end]).strip() + "\n"
