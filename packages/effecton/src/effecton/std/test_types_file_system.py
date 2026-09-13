"""Type-level pins for the FileSystem service. Nothing here runs: ty checks
the function bodies and pytest never calls them, so nothing touches the disk."""

from typing import Never, assert_type

import effecton as E

FS = E.FileSystem


def _every_op_carries_its_own_error_union() -> None:
    fs: FS.Protocol = FS.SyncLive()
    path = E.Path("/a")

    assert_type(fs.exists(path), E.Effect[bool, FS.PermissionDenied])
    assert_type(fs.stat(path), E.Effect[FS.FileInfo, FS.StatError])
    assert_type(fs.read_file(path), E.Effect[bytes, FS.ReadError])
    assert_type(fs.read_file_string(path), E.Effect[str, FS.ReadError])
    assert_type(fs.write_file(path, b"x"), E.Effect[None, FS.WriteError])
    assert_type(fs.write_file_string(path, "x"), E.Effect[None, FS.WriteError])
    assert_type(fs.make_directory(path), E.Effect[None, FS.MakeDirectoryError])
    assert_type(
        fs.make_directory(path, recursive=True), E.Effect[None, FS.MakeDirectoryError]
    )
    assert_type(
        fs.read_directory(path), E.Effect[tuple[E.Path, ...], FS.ReadDirectoryError]
    )
    assert_type(fs.remove(path), E.Effect[None, FS.RemoveError])
    assert_type(fs.rename(path, path), E.Effect[None, FS.RenameError])
    assert_type(fs.copy_file(path, path), E.Effect[None, FS.CopyFileError])
    assert_type(fs.symlink(path, path), E.Effect[None, FS.SymlinkError])
    assert_type(fs.read_link(path), E.Effect[E.Path, FS.StatError])


def _the_service_is_an_explicit_requirement() -> None:
    @E.gen
    def read_config() -> E.EffectGen[str, FS.ReadError, FS.Protocol]:
        fs = yield from E.require(FS.Protocol)

        return (yield from fs.read_file_string(E.Path("/config.toml")))

    assert_type(E.require(FS.Protocol), E.Effect[FS.Protocol, Never, FS.Protocol])
    assert_type(
        read_config().provide(FS.Protocol)(FS.SyncLive()),
        E.Effect[str, FS.ReadError],
    )
    assert_type(
        read_config().provide(FS.Protocol)(FS.AsyncLive()),
        E.Effect[str, FS.ReadError],
    )
    assert_type(
        read_config().provide(FS.Protocol)(FS.Test()), E.Effect[str, FS.ReadError]
    )
    assert_type(
        read_config().catch(FS.FileNotFound)(lambda _: E.success("")),
        E.Effect[str, FS.PermissionDenied | FS.PathIsADirectory, FS.Protocol],
    )

    # The requirement must be provided before running.
    E.run_sync(read_config())  # ty: ignore[invalid-argument-type]


def _test_state_is_typed() -> None:
    fs = FS.Test(files={E.Path("/a"): "text", E.Path("/b"): b"bytes"})

    assert_type(fs.files, dict[E.Path, bytes | str])
    assert_type(fs.directories, set[E.Path])
    assert_type(fs.links, dict[E.Path, E.Path])


def _file_system_negative() -> None:
    fs: FS.Protocol = FS.SyncLive()
    path = E.Path("/a")

    # Only a FileSystem implementation can be provided as the FileSystem.
    E.require(FS.Protocol).provide(FS.Protocol)(object())  # ty: ignore[invalid-argument-type]

    # Paths are E.Path values, never strings.
    fs.read_file("/a")  # ty: ignore[invalid-argument-type]

    # Bytes and strings each have their own op.
    fs.write_file(path, "text")  # ty: ignore[invalid-argument-type]
    fs.write_file_string(path, b"bytes")  # ty: ignore[invalid-argument-type]

    # recursive is keyword-only.
    fs.make_directory(path, True)  # ty: ignore[too-many-positional-arguments]

    # Implementations are leaves: none can be subclassed.
    class CustomSyncLive(FS.SyncLive):  # ty: ignore[subclass-of-final-class]
        pass

    class CustomAsyncLive(FS.AsyncLive):  # ty: ignore[subclass-of-final-class]
        pass

    class CustomTest(FS.Test):  # ty: ignore[subclass-of-final-class]
        pass
