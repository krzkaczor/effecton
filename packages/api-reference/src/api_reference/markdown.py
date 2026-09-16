"""Turn a Reference into the Markdown page vocs renders at /api."""

import re

from api_reference import signature
from api_reference.collect import Reference, Symbol

FRONTMATTER = """\
---
title: API Reference
description: Every public name reachable from import effecton as E.
---
"""

FENCE = "```python notwoslash"


def render_page(reference: Reference) -> str:
    parts = [FRONTMATTER, "# API Reference"]
    for section in reference.sections:
        parts += ["", f"## {section.title}"]
        for symbol in section.symbols:
            parts += symbol_block(symbol)
    return "\n".join(parts) + "\n"


def symbol_block(symbol: Symbol) -> list[str]:
    short = symbol.display.rsplit(".", 1)[-1]
    lines = ["", f"### {symbol.display}"]
    lines += definition(signature.render(symbol.obj, short))
    if symbol.note is not None:
        lines += ["", symbol.note]
    lines += docstring(symbol.obj.docstring)
    for member in symbol.members:
        lines += ["", f"#### {member.display}"]
        lines += definition(
            signature.render(member.obj, member.display.rsplit(".", 1)[-1])
        )
        lines += docstring(member.obj.docstring)
    return lines


def definition(text: str) -> list[str]:
    if not text:
        return []
    return ["", FENCE, text, "```"]


def docstring(doc: object) -> list[str]:
    value = getattr(doc, "value", None)
    if not isinstance(value, str) or not value.strip():
        return []
    return ["", docstring_to_markdown(value)]


def docstring_to_markdown(text: str) -> str:
    """Plain-prose docstrings need only RST literals turned into code spans."""
    return re.sub(r"``([^`]+)``", r"`\1`", text.strip())
