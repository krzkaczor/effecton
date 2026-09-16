---
title: FileSystem
description: Reading and writing the disk through the explicit FileSystem requirement, with live and in-memory implementations.
---

# FileSystem

`E.FileSystem` reads and writes the disk. It is an explicit requirement: a program that needs it says so in `R` through `E.require(E.FileSystem.Protocol)`, and forgetting to provide an implementation is a type error rather than a surprise write to the real disk. Its methods follow the names of Effect-TS's FileSystem and each returns an effect with a precise error union: `exists`, `stat`, `read_file`, `read_file_string`, `write_file`, `write_file_string`, `make_directory(path, recursive=...)`, `read_directory`, `remove(path, recursive=...)`, `rename`, `copy_file`, `symlink(target, link)` and `read_link`. The working and home directories are not file I/O and live on `E.Process`. Errors are cause-specific (`FileNotFound`, `PermissionDenied`, `PathIsADirectory`, `PathIsNotADirectory`, `PathAlreadyExists`, `DirectoryNotEmpty`), so `catch(E.FileSystem.FileNotFound)` handles exactly the missing-file case; anything else the disk can do, such as running out of space, stays a defect.

```python
import effecton as E


# ---cut---
@E.gen
def read_config(
    root: E.Path,
) -> E.EffectGen[str, E.FileSystem.ReadError, E.FileSystem.Protocol]:
    fs = yield from E.require(E.FileSystem.Protocol)

    return (yield from fs.read_file_string(root / "config.toml"))


program = read_config(E.Path("/repo"))
#  ^?
E.run_sync(program.provide(E.FileSystem.Protocol)(E.FileSystem.SyncLive()))
```

There are two live implementations, one per runner, like the Clock: `E.FileSystem.SyncLive` blocks the thread on the `os` calls and suits `run_sync`; `E.FileSystem.AsyncLive` makes the same calls through [aiofiles](https://github.com/Tinche/aiofiles), so the loop keeps turning under `run_async` and `run_main`. aiofiles is a dependency of effecton, so both implementations are always available.

In tests, provide `E.FileSystem.Test`, an in-memory tree seeded with `files` (text or bytes), `directories` and `links`; every ancestor of a seeded path is created for you. It enforces the same rules as the disk, so a program gets the same `Exit` against `Test` as against a live implementation, and its state stays inspectable afterwards:

```python
import effecton as E


@E.gen
def read_config(
    root: E.Path,
) -> E.EffectGen[str, E.FileSystem.ReadError, E.FileSystem.Protocol]:
    fs = yield from E.require(E.FileSystem.Protocol)

    return (yield from fs.read_file_string(root / "config.toml"))


# ---cut---
def test_reads_the_config():
    fs = E.FileSystem.Test(files={E.Path("/repo/config.toml"): "[packages]\n"})

    result = E.run_sync(read_config(E.Path("/repo")).provide(E.FileSystem.Protocol)(fs))

    assert result == "[packages]\n"
```

More examples: [`test_file_system.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_file_system.py).
