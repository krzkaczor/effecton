"""Every scenario runs against SyncLive, AsyncLive and Test through the fs
fixture, with the tree built through the service itself, so the three
implementations are pinned to the same Exit for the same story. Only the
permission tests need the real disk (chmod) and run against the Lives."""

import os

import pytest

import effecton as E

FS = E.FileSystem
TEST_ROOT = E.Path("/work")


@pytest.fixture(params=["sync", "async", "test"])
def fs(request) -> FS.Protocol:
    match request.param:
        case "sync":
            return FS.SyncLive()
        case "async":
            return FS.AsyncLive()
        case _:
            return FS.Test(directories={TEST_ROOT})


@pytest.fixture(params=["sync", "async"])
def live(request) -> FS.Protocol:
    return FS.SyncLive() if request.param == "sync" else FS.AsyncLive()


@pytest.fixture
def root(fs, tmp_path) -> E.Path:
    return TEST_ROOT if isinstance(fs, FS.Test) else E.Path(str(tmp_path))


def run(fs, effect):
    if isinstance(fs, FS.AsyncLive):
        return E.run_async_exit(effect)
    return E.run_sync_exit(effect)


def ok(value=None):
    return E.Succeeded(value=value)


def failed(error):
    return E.Failure(cause=E.Fail(error))


def test_write_then_read_string_round_trips(fs, root):
    path = root / "note.md"

    run(fs, fs.write_file_string(path, "hello"))
    result = run(fs, fs.read_file_string(path))

    assert result == ok("hello")


def test_bytes_and_strings_share_one_file(fs, root):
    path = root / "data.bin"

    run(fs, fs.write_file(path, "héllo".encode()))
    as_bytes = run(fs, fs.read_file(path))
    as_text = run(fs, fs.read_file_string(path))

    assert as_bytes == ok("héllo".encode())
    assert as_text == ok("héllo")


def test_write_overwrites(fs, root):
    path = root / "note.md"

    run(fs, fs.write_file_string(path, "one"))
    run(fs, fs.write_file_string(path, "two"))

    assert run(fs, fs.read_file_string(path)) == ok("two")


def test_reading_a_missing_file_fails(fs, root):
    path = root / "missing.md"

    result = run(fs, fs.read_file_string(path))

    assert result == failed(FS.FileNotFound(path=path))


def test_reading_a_directory_fails(fs, root):
    result = run(fs, fs.read_file(root))

    assert result == failed(FS.PathIsADirectory(path=root))


def test_writing_under_a_missing_parent_fails(fs, root):
    path = root / "missing" / "note.md"

    result = run(fs, fs.write_file_string(path, "x"))

    assert result == failed(FS.FileNotFound(path=path))


def test_writing_under_a_file_fails(fs, root):
    run(fs, fs.write_file_string(root / "file", "x"))
    path = root / "file" / "note.md"

    result = run(fs, fs.write_file_string(path, "x"))

    assert result == failed(FS.PathIsNotADirectory(path=path))


def test_writing_onto_a_directory_fails(fs, root):
    result = run(fs, fs.write_file(root, b"x"))

    assert result == failed(FS.PathIsADirectory(path=root))


def test_exists_reflects_writes(fs, root):
    path = root / "note.md"

    before = run(fs, fs.exists(path))
    run(fs, fs.write_file_string(path, "x"))
    after = run(fs, fs.exists(path))

    assert (before, after) == (ok(False), ok(True))


def test_exists_is_false_under_a_file(fs, root):
    run(fs, fs.write_file_string(root / "file", "x"))

    result = run(fs, fs.exists(root / "file" / "child"))

    assert result == ok(False)


def test_a_dangling_symlink_exists(fs, root):
    link = root / "link"
    run(fs, fs.symlink(root / "missing", link))

    result = run(fs, fs.exists(link))

    assert result == ok(True)


def test_stat_describes_the_entry_itself(fs, root):
    run(fs, fs.write_file(root / "file", b"12345"))
    run(fs, fs.make_directory(root / "dir"))
    run(fs, fs.symlink(root / "file", root / "link"))

    file = run(fs, fs.stat(root / "file"))
    directory = run(fs, fs.stat(root / "dir"))
    link = run(fs, fs.stat(root / "link"))

    assert isinstance(file, E.Succeeded)
    assert (file.value.type, file.value.size) == ("file", 5)
    assert file.value.modified_at.tzinfo is not None
    assert isinstance(directory, E.Succeeded)
    assert directory.value.type == "directory"
    assert isinstance(link, E.Succeeded)
    assert link.value.type == "symlink"


def test_stat_of_a_missing_path_fails(fs, root):
    path = root / "missing"

    result = run(fs, fs.stat(path))

    assert result == failed(FS.FileNotFound(path=path))


def test_make_directory_creates_one_level(fs, root):
    path = root / "dir"

    result = run(fs, fs.make_directory(path))

    assert result == ok()
    assert run(fs, fs.read_directory(root)) == ok((path,))


def test_make_directory_fails_when_the_path_is_taken(fs, root):
    path = root / "dir"
    run(fs, fs.make_directory(path))

    again = run(fs, fs.make_directory(path))
    recursive_over_file = run(
        fs,
        fs.write_file_string(root / "file", "x").flat_map(
            lambda _: fs.make_directory(root / "file", recursive=True)
        ),
    )

    assert again == failed(FS.PathAlreadyExists(path=path))
    assert recursive_over_file == failed(FS.PathAlreadyExists(path=root / "file"))


def test_make_directory_fails_under_a_missing_parent(fs, root):
    path = root / "missing" / "dir"

    result = run(fs, fs.make_directory(path))

    assert result == failed(FS.FileNotFound(path=path))


def test_make_directory_fails_under_a_file(fs, root):
    run(fs, fs.write_file_string(root / "file", "x"))
    path = root / "file" / "dir"

    plain = run(fs, fs.make_directory(path))
    recursive = run(fs, fs.make_directory(path, recursive=True))

    assert plain == failed(FS.PathIsNotADirectory(path=path))
    assert recursive == failed(FS.PathIsNotADirectory(path=path))


def test_recursive_make_directory_creates_parents_and_is_idempotent(fs, root):
    path = root / "a" / "b" / "c"

    first = run(fs, fs.make_directory(path, recursive=True))
    second = run(fs, fs.make_directory(path, recursive=True))

    assert (first, second) == (ok(), ok())
    assert run(fs, fs.read_directory(root / "a")) == ok((root / "a" / "b",))


def test_read_directory_lists_full_paths_sorted(fs, root):
    run(fs, fs.write_file_string(root / "b.md", "b"))
    run(fs, fs.write_file_string(root / "a.md", "a"))
    run(fs, fs.make_directory(root / "c"))
    run(fs, fs.symlink(root / "a.md", root / "d"))

    result = run(fs, fs.read_directory(root))

    assert result == ok((root / "a.md", root / "b.md", root / "c", root / "d"))


def test_read_directory_of_an_empty_directory_is_empty(fs, root):
    run(fs, fs.make_directory(root / "empty"))

    result = run(fs, fs.read_directory(root / "empty"))

    assert result == ok(())


def test_read_directory_fails_for_a_missing_path_and_for_a_file(fs, root):
    run(fs, fs.write_file_string(root / "file", "x"))

    missing = run(fs, fs.read_directory(root / "missing"))
    file = run(fs, fs.read_directory(root / "file"))

    assert missing == failed(FS.FileNotFound(path=root / "missing"))
    assert file == failed(FS.PathIsNotADirectory(path=root / "file"))


def test_remove_deletes_a_file_and_an_empty_directory(fs, root):
    run(fs, fs.write_file_string(root / "file", "x"))
    run(fs, fs.make_directory(root / "dir"))

    file = run(fs, fs.remove(root / "file"))
    directory = run(fs, fs.remove(root / "dir"))

    assert (file, directory) == (ok(), ok())
    assert run(fs, fs.read_directory(root)) == ok(())


def test_remove_refuses_a_non_empty_directory_unless_recursive(fs, root):
    run(fs, fs.make_directory(root / "dir" / "sub", recursive=True))
    run(fs, fs.write_file_string(root / "dir" / "sub" / "file", "x"))

    plain = run(fs, fs.remove(root / "dir"))
    recursive = run(fs, fs.remove(root / "dir", recursive=True))

    assert plain == failed(FS.DirectoryNotEmpty(path=root / "dir"))
    assert recursive == ok()
    assert run(fs, fs.exists(root / "dir")) == ok(False)
    assert run(fs, fs.exists(root / "dir" / "sub" / "file")) == ok(False)


def test_remove_of_a_missing_path_fails(fs, root):
    result = run(fs, fs.remove(root / "missing"))

    assert result == failed(FS.FileNotFound(path=root / "missing"))


def test_remove_of_a_symlink_keeps_the_target(fs, root):
    run(fs, fs.make_directory(root / "dir"))
    run(fs, fs.write_file_string(root / "dir" / "file", "x"))
    run(fs, fs.symlink(root / "dir", root / "link"))

    result = run(fs, fs.remove(root / "link", recursive=True))

    assert result == ok()
    assert run(fs, fs.exists(root / "link")) == ok(False)
    assert run(fs, fs.read_file_string(root / "dir" / "file")) == ok("x")


def test_rename_moves_a_file_and_replaces_an_existing_one(fs, root):
    run(fs, fs.write_file_string(root / "old", "new content"))
    run(fs, fs.write_file_string(root / "taken", "old content"))

    moved = run(fs, fs.rename(root / "old", root / "new"))
    replaced = run(fs, fs.rename(root / "new", root / "taken"))

    assert (moved, replaced) == (ok(), ok())
    assert run(fs, fs.read_directory(root)) == ok((root / "taken",))
    assert run(fs, fs.read_file_string(root / "taken")) == ok("new content")


def test_rename_moves_a_directory_with_its_contents(fs, root):
    run(fs, fs.make_directory(root / "old" / "sub", recursive=True))
    run(fs, fs.write_file_string(root / "old" / "sub" / "file", "x"))

    result = run(fs, fs.rename(root / "old", root / "new"))

    assert result == ok()
    assert run(fs, fs.exists(root / "old")) == ok(False)
    assert run(fs, fs.read_file_string(root / "new" / "sub" / "file")) == ok("x")


def test_rename_onto_the_wrong_kind_fails(fs, root):
    run(fs, fs.write_file_string(root / "file", "x"))
    run(fs, fs.make_directory(root / "dir"))
    run(fs, fs.make_directory(root / "full"))
    run(fs, fs.write_file_string(root / "full" / "inner", "x"))
    run(fs, fs.make_directory(root / "empty"))

    file_onto_dir = run(fs, fs.rename(root / "file", root / "dir"))
    dir_onto_file = run(fs, fs.rename(root / "dir", root / "file"))
    dir_onto_full = run(fs, fs.rename(root / "dir", root / "full"))
    dir_onto_empty = run(fs, fs.rename(root / "dir", root / "empty"))

    assert file_onto_dir == failed(FS.PathIsADirectory(path=root / "dir"))
    assert dir_onto_file == failed(FS.PathIsNotADirectory(path=root / "file"))
    assert dir_onto_full == failed(FS.DirectoryNotEmpty(path=root / "full"))
    assert dir_onto_empty == ok()
    assert run(fs, fs.exists(root / "dir")) == ok(False)


def test_rename_reports_the_side_that_is_missing(fs, root):
    run(fs, fs.write_file_string(root / "file", "x"))

    missing_source = run(fs, fs.rename(root / "missing", root / "new"))
    missing_parent = run(fs, fs.rename(root / "file", root / "nowhere" / "new"))

    assert missing_source == failed(FS.FileNotFound(path=root / "missing"))
    assert missing_parent == failed(FS.FileNotFound(path=root / "nowhere" / "new"))


def test_copy_file_duplicates_the_content(fs, root):
    run(fs, fs.write_file_string(root / "src", "x"))

    result = run(fs, fs.copy_file(root / "src", root / "dst"))

    assert result == ok()
    assert run(fs, fs.read_file_string(root / "src")) == ok("x")
    assert run(fs, fs.read_file_string(root / "dst")) == ok("x")


def test_copy_file_reports_the_side_that_failed(fs, root):
    run(fs, fs.write_file_string(root / "src", "x"))
    run(fs, fs.make_directory(root / "dir"))

    missing_source = run(fs, fs.copy_file(root / "missing", root / "dst"))
    source_is_dir = run(fs, fs.copy_file(root / "dir", root / "dst"))
    target_is_dir = run(fs, fs.copy_file(root / "src", root / "dir"))
    missing_parent = run(fs, fs.copy_file(root / "src", root / "nowhere" / "dst"))

    assert missing_source == failed(FS.FileNotFound(path=root / "missing"))
    assert source_is_dir == failed(FS.PathIsADirectory(path=root / "dir"))
    assert target_is_dir == failed(FS.PathIsADirectory(path=root / "dir"))
    assert missing_parent == failed(FS.FileNotFound(path=root / "nowhere" / "dst"))


def test_symlink_points_at_its_target_and_reads_through(fs, root):
    run(fs, fs.write_file_string(root / "file", "x"))

    created = run(fs, fs.symlink(root / "file", root / "link"))

    assert created == ok()
    assert run(fs, fs.read_link(root / "link")) == ok(root / "file")
    assert run(fs, fs.read_file_string(root / "link")) == ok("x")


def test_reading_through_a_dangling_symlink_fails(fs, root):
    run(fs, fs.symlink(root / "missing", root / "link"))

    result = run(fs, fs.read_file_string(root / "link"))

    assert result == failed(FS.FileNotFound(path=root / "link"))


def test_symlink_fails_when_the_link_path_is_taken_or_has_no_parent(fs, root):
    run(fs, fs.symlink(root / "missing", root / "link"))

    taken = run(fs, fs.symlink(root / "other", root / "link"))
    no_parent = run(fs, fs.symlink(root / "other", root / "nowhere" / "link"))

    assert taken == failed(FS.PathAlreadyExists(path=root / "link"))
    assert no_parent == failed(FS.FileNotFound(path=root / "nowhere" / "link"))


def test_read_link_fails_for_a_missing_path_and_dies_for_a_file(fs, root):
    run(fs, fs.write_file_string(root / "file", "x"))

    missing = run(fs, fs.read_link(root / "missing"))
    file = run(fs, fs.read_link(root / "file"))

    assert missing == failed(FS.FileNotFound(path=root / "missing"))
    assert isinstance(file, E.Failure)
    assert isinstance(file.cause, E.Die)
    assert isinstance(file.cause.defect, OSError)


def test_effects_are_reusable_values(fs, root):
    path = root / "file"
    write = fs.write_file_string(path, "again")

    run(fs, write)
    run(fs, fs.remove(path))
    rerun = run(fs, write)

    assert rerun == ok()
    assert run(fs, fs.read_file_string(path)) == ok("again")


def test_async_live_dies_under_run_sync():
    result = E.run_sync_exit(FS.AsyncLive().exists(E.Path("/")))

    assert result == E.Failure(cause=E.Die(defect=E.AsyncEffectInSyncRun()))


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file modes")
def test_live_exists_fails_without_search_permission_on_the_parent(live, tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o000)
    probe = E.Path(str(locked / "child"))

    result = run(live, live.exists(probe))
    locked.chmod(0o755)

    assert result == failed(FS.PermissionDenied(path=probe))


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file modes")
def test_live_writes_fail_without_write_permission_on_the_parent(live, tmp_path):
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    readonly.chmod(0o500)
    directory = E.Path(str(readonly))

    write = run(live, live.write_file_string(directory / "file", "x"))
    mkdir = run(live, live.make_directory(directory / "dir"))
    link = run(live, live.symlink(directory, directory / "link"))
    readonly.chmod(0o755)

    assert write == failed(FS.PermissionDenied(path=directory / "file"))
    assert mkdir == failed(FS.PermissionDenied(path=directory / "dir"))
    assert link == failed(FS.PermissionDenied(path=directory / "link"))


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file modes")
def test_live_reads_fail_without_read_permission(live, tmp_path):
    secret = tmp_path / "secret"
    secret.write_text("x")
    secret.chmod(0o000)
    path = E.Path(str(secret))

    result = run(live, live.read_file_string(path))
    secret.chmod(0o644)

    assert result == failed(FS.PermissionDenied(path=path))


def test_test_seeds_every_ancestor_directory():
    fs = FS.Test(files={E.Path("/repo/.changeset/one.md"): "x"})

    assert E.Path("/repo/.changeset") in fs.directories
    assert E.Path("/repo") in fs.directories
    assert E.Path("/") in fs.directories
    assert E.run_sync(fs.read_directory(E.Path("/repo"))) == (
        E.Path("/repo/.changeset"),
    )


def test_test_keeps_text_as_text_and_bytes_as_bytes():
    fs = FS.Test()

    E.run_sync(fs.write_file_string(E.Path("/note.md"), "text"))
    E.run_sync(fs.write_file(E.Path("/blob"), b"\x00\x01"))
    E.run_sync(fs.write_file_string(E.Path("/latin"), "é", encoding="latin-1"))

    assert fs.files == {
        E.Path("/note.md"): "text",
        E.Path("/blob"): b"\x00\x01",
        E.Path("/latin"): "é".encode("latin-1"),
    }
    assert E.run_sync(fs.read_file(E.Path("/note.md"))) == b"text"
    assert E.run_sync(fs.read_file_string(E.Path("/latin"), encoding="latin-1")) == "é"


def test_test_symlink_loops_are_a_defect():
    fs = FS.Test(links={E.Path("/a"): E.Path("/b"), E.Path("/b"): E.Path("/a")})

    result = E.run_sync_exit(fs.read_file(E.Path("/a")))

    assert isinstance(result, E.Failure)
    assert isinstance(result.cause, E.Die)
