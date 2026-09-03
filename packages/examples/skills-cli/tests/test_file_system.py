from pathlib import Path

import effecton as E
from skills_cli import file_system as FileSystem


def test_live_exists_reflects_the_real_file_system(tmp_path):
    fs = FileSystem.Live()
    target = tmp_path / "file.txt"

    before = E.run_sync(fs.exists(target))
    target.write_text("hi")
    after = E.run_sync(fs.exists(target))

    assert before == E.Succeeded(value=False)
    assert after == E.Succeeded(value=True)


def test_live_mkdir_creates_nested_directories_and_is_idempotent(tmp_path):
    fs = FileSystem.Live()
    nested = tmp_path / "a" / "b" / "c"

    first = E.run_sync(fs.mkdir(nested))
    second = E.run_sync(fs.mkdir(nested))

    assert first == E.Succeeded(value=None)
    assert second == E.Succeeded(value=None)
    assert nested.is_dir()


def test_live_write_text_round_trips(tmp_path):
    fs = FileSystem.Live()
    target = tmp_path / "SKILL.md"

    result = E.run_sync(fs.write_text(target, "skill body"))

    assert result == E.Succeeded(value=None)
    assert target.read_text() == "skill body"


def test_live_symlink_points_at_the_target(tmp_path):
    fs = FileSystem.Live()
    target = tmp_path / "skill-dir"
    target.mkdir()
    link = tmp_path / "link"

    result = E.run_sync(fs.symlink(link, target))

    assert result == E.Succeeded(value=None)
    assert link.is_symlink()
    assert link.readlink() == target


def test_live_effects_are_reusable_values(tmp_path):
    fs = FileSystem.Live()
    target = tmp_path / "file.txt"
    write = fs.write_text(target, "again")

    E.run_sync(write)
    target.unlink()
    rerun = E.run_sync(write)

    assert rerun == E.Succeeded(value=None)
    assert target.read_text() == "again"


def test_live_exists_counts_a_dangling_symlink_as_existing(tmp_path):
    fs = FileSystem.Live()
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "missing", target_is_directory=True)

    result = E.run_sync(fs.exists(link))

    assert result == E.Succeeded(value=True)


def test_live_exists_fails_without_search_permission_on_the_parent(tmp_path):
    fs = FileSystem.Live()
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o000)
    probe = locked / "child"

    result = E.run_sync(fs.exists(probe))
    locked.chmod(0o755)

    assert result == E.Failure(cause=E.Fail(FileSystem.PermissionDenied(path=probe)))


def test_live_mkdir_fails_without_write_permission_on_the_parent(tmp_path):
    fs = FileSystem.Live()
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    readonly.chmod(0o500)
    target = readonly / "new"

    result = E.run_sync(fs.mkdir(target))
    readonly.chmod(0o755)

    assert result == E.Failure(cause=E.Fail(FileSystem.PermissionDenied(path=target)))


def test_live_mkdir_fails_when_a_file_occupies_the_path(tmp_path):
    fs = FileSystem.Live()
    occupied = tmp_path / "occupied"
    occupied.write_text("not a directory")

    result = E.run_sync(fs.mkdir(occupied))

    assert result == E.Failure(
        cause=E.Fail(FileSystem.PathIsNotADirectory(path=occupied))
    )


def test_live_mkdir_fails_when_a_parent_is_a_file(tmp_path):
    fs = FileSystem.Live()
    parent = tmp_path / "file"
    parent.write_text("not a directory")
    target = parent / "sub"

    result = E.run_sync(fs.mkdir(target))

    assert result == E.Failure(
        cause=E.Fail(FileSystem.PathIsNotADirectory(path=target))
    )


def test_live_write_text_fails_without_write_permission_on_the_parent(tmp_path):
    fs = FileSystem.Live()
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    readonly.chmod(0o500)
    target = readonly / "SKILL.md"

    result = E.run_sync(fs.write_text(target, "body"))
    readonly.chmod(0o755)

    assert result == E.Failure(cause=E.Fail(FileSystem.PermissionDenied(path=target)))


def test_live_write_text_fails_when_the_path_is_a_directory(tmp_path):
    fs = FileSystem.Live()
    target = tmp_path / "adir"
    target.mkdir()

    result = E.run_sync(fs.write_text(target, "body"))

    assert result == E.Failure(cause=E.Fail(FileSystem.PathIsADirectory(path=target)))


def test_live_symlink_fails_without_write_permission_on_the_parent(tmp_path):
    fs = FileSystem.Live()
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    readonly.chmod(0o500)
    link = readonly / "link"

    result = E.run_sync(fs.symlink(link, tmp_path / "target"))
    readonly.chmod(0o755)

    assert result == E.Failure(cause=E.Fail(FileSystem.PermissionDenied(path=link)))


def test_live_symlink_fails_when_the_link_path_is_taken_by_a_dangling_symlink(
    tmp_path,
):
    fs = FileSystem.Live()
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "missing", target_is_directory=True)

    result = E.run_sync(fs.symlink(link, tmp_path / "target"))

    assert result == E.Failure(cause=E.Fail(FileSystem.PathAlreadyExists(path=link)))


def test_test_impl_records_mutations():
    fs = FileSystem.Test()

    E.run_sync(fs.mkdir(Path("/skills")))
    E.run_sync(fs.write_text(Path("/skills/SKILL.md"), "body"))
    E.run_sync(fs.symlink(Path("/link"), Path("/skills")))

    assert fs.dirs == {Path("/skills")}
    assert fs.files == {Path("/skills/SKILL.md"): "body"}
    assert fs.links == {Path("/link"): Path("/skills")}


def test_test_impl_exists_consults_files_dirs_and_links():
    fs = FileSystem.Test(
        files={Path("/f"): "x"}, dirs={Path("/d")}, links={Path("/l"): Path("/d")}
    )

    assert E.run_sync(fs.exists(Path("/f"))) == E.Succeeded(value=True)
    assert E.run_sync(fs.exists(Path("/d"))) == E.Succeeded(value=True)
    assert E.run_sync(fs.exists(Path("/l"))) == E.Succeeded(value=True)
    assert E.run_sync(fs.exists(Path("/missing"))) == E.Succeeded(value=False)
