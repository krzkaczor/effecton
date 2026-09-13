"""Type-level pins for Path. Nothing here runs: ty checks the function
bodies and pytest never calls them."""

from typing import assert_type

import effecton as E


def _slash_and_pieces_keep_the_path_type() -> None:
    assert_type(E.Path("/a") / "b", E.Path)
    assert_type(E.Path("/a") / E.Path("b"), E.Path)
    assert_type(E.Path("/a/b").parent, E.Path)
    assert_type(E.Path("/a/b").parents, tuple[E.Path, ...])
    assert_type(E.Path("/a/b.md").name, str)
    assert_type(E.Path("/a/b.md").suffix, str)
    assert_type(E.Path("/a/b.md").stem, str)
    assert_type(E.Path("/a/b.md").parts, tuple[str, ...])
    assert_type(str(E.Path("/a")), str)


def _path_negative() -> None:
    # Segments are strings.
    E.Path(1)  # ty: ignore[invalid-argument-type]

    # Only strings and Paths join.
    E.Path("/a") / 1  # ty: ignore[unsupported-operator]

    # No I/O lives on a Path: read, write and probe through E.FileSystem.
    E.Path("/a").read_text()  # ty: ignore[unresolved-attribute]
    E.Path("/a").exists()  # ty: ignore[unresolved-attribute]
    E.Path("/a").mkdir()  # ty: ignore[unresolved-attribute]

    # Path is a leaf: it cannot be subclassed.
    class CustomPath(E.Path):  # ty: ignore[subclass-of-final-class]
        pass
