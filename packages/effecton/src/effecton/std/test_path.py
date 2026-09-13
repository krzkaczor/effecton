import dataclasses

import pytest

import effecton as E


def test_slash_joins_segments():
    joined = E.Path("/repo") / ".changeset" / "config.toml"

    assert joined == E.Path("/repo/.changeset/config.toml")


def test_slash_accepts_a_path_on_the_right():
    joined = E.Path("/repo") / E.Path("a/b")

    assert joined == E.Path("/repo/a/b")


def test_an_absolute_right_hand_side_replaces_the_left():
    joined = E.Path("/repo") / "/etc"

    assert joined == E.Path("/etc")


def test_construction_normalizes_separators_and_dots():
    assert E.Path("/repo//a/./b/") == E.Path("/repo/a/b")
    assert E.Path("/repo", "a", "b") == E.Path("/repo/a/b")


def test_equal_paths_hash_equal():
    index = {E.Path("/a/b"): 1}

    assert index[E.Path("/a") / "b"] == 1


def test_paths_sort_by_their_parts():
    ordered = sorted([E.Path("/b"), E.Path("/a/c"), E.Path("/a")])

    assert ordered == [E.Path("/a"), E.Path("/a/c"), E.Path("/b")]


def test_str_and_repr():
    path = E.Path("/a") / "b"

    assert str(path) == "/a/b"
    assert repr(path) == "Path('/a/b')"


def test_pieces_of_a_file_path():
    path = E.Path("/repo/.changeset/note.md")

    assert path.parent == E.Path("/repo/.changeset")
    assert path.parents == (E.Path("/repo/.changeset"), E.Path("/repo"), E.Path("/"))
    assert path.name == "note.md"
    assert path.suffix == ".md"
    assert path.stem == "note"
    assert path.parts == ("/", "repo", ".changeset", "note.md")


def test_the_root_is_its_own_parent_and_has_no_parents():
    root = E.Path("/")

    assert root.parent == root
    assert root.parents == ()


def test_paths_are_immutable():
    path = E.Path("/a")

    with pytest.raises(dataclasses.FrozenInstanceError):
        path.name = "b"  # ty: ignore[invalid-assignment]
