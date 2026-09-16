import griffe

from api_reference import markdown
from api_reference.collect import Member, Reference, Section, Symbol

CODE = (
    "class Box:\n"
    '    """Holds ``one`` value."""\n'
    "    def get(self) -> int:\n"
    '        """Read it."""\n'
)


def page():
    with griffe.temporary_visited_module(CODE, module_name="m") as module:
        box = module["Box"]
        get = module["Box.get"]
        assert isinstance(box, griffe.Class) and isinstance(get, griffe.Function)
        symbol = Symbol("E.Box", box, (Member("E.Box.get", get),), note="A note.")
        reference = Reference((Section("Core", (symbol,)), Section("Empty", ())))
        return markdown.render_page(reference)


def test_page_starts_with_frontmatter_and_title():
    text = page()

    assert text.startswith("---\ntitle: API Reference\n")
    assert "\n# API Reference\n\n## Core\n" in text


def test_sections_symbols_and_members_nest_as_headings():
    text = page()

    assert "\n## Core\n\n### E.Box\n" in text
    assert "\n#### E.Box.get\n" in text
    assert text.endswith("\n## Empty\n")


def test_every_fence_skips_the_type_gate():
    text = page()

    fences = [
        line for line in text.splitlines() if line.startswith("```") and line != "```"
    ]
    assert fences and all(line == "```python notwoslash" for line in fences)


def test_note_and_docstring_follow_the_signature():
    text = page()

    assert "class Box:\n    ...\n```\n\nA note.\n\nHolds `one` value.\n" in text
    assert "def get() -> int\n```\n\nRead it.\n" in text


def test_docstring_literals_become_code_spans():
    assert (
        markdown.docstring_to_markdown("  Use ``E.gen`` here.\n") == "Use `E.gen` here."
    )
