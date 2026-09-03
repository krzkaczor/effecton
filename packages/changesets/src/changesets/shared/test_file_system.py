import effecton as E
from changesets.shared import file_system as FileSystem
from changesets.shared.file_system import FileNotFound


def test_write_then_read_roundtrips(tmp_path):
    fs = FileSystem.Live()
    path = tmp_path / "note.md"

    E.run_sync(fs.write_text(path, "hello"))
    result = E.run_sync(fs.read_text(path))

    assert result == E.Succeeded(value="hello")


def test_reading_a_missing_file_fails(tmp_path):
    fs = FileSystem.Live()
    path = tmp_path / "missing.md"

    result = E.run_sync(fs.read_text(path))

    assert result == E.Failure(cause=E.Fail(FileNotFound(path=path)))


def test_exists_reflects_the_real_file_system(tmp_path):
    fs = FileSystem.Live()
    present = tmp_path / "present.md"
    present.write_text("x")

    assert E.run_sync(fs.exists(present)) == E.Succeeded(value=True)
    assert E.run_sync(fs.exists(tmp_path / "absent.md")) == E.Succeeded(value=False)


def test_list_markdown_returns_sorted_md_files_only(tmp_path):
    fs = FileSystem.Live()
    (tmp_path / "b.md").write_text("b")
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "config.toml").write_text("")

    result = E.run_sync(fs.list_markdown(tmp_path))

    assert result == E.Succeeded(value=(tmp_path / "a.md", tmp_path / "b.md"))


def test_listing_a_missing_directory_fails(tmp_path):
    fs = FileSystem.Live()
    directory = tmp_path / "absent"

    result = E.run_sync(fs.list_markdown(directory))

    assert result == E.Failure(cause=E.Fail(FileNotFound(path=directory)))


def test_delete_removes_the_file(tmp_path):
    fs = FileSystem.Live()
    path = tmp_path / "note.md"
    path.write_text("x")

    result = E.run_sync(fs.delete(path))

    assert result == E.Succeeded(value=None)
    assert not path.exists()


def test_deleting_a_missing_file_fails(tmp_path):
    fs = FileSystem.Live()
    path = tmp_path / "missing.md"

    result = E.run_sync(fs.delete(path))

    assert result == E.Failure(cause=E.Fail(FileNotFound(path=path)))
