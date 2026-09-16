---
title: Path
description: The immutable, I/O-free path value that every effecton file operation takes.
---

# Path

`E.Path` is the only path type effecton code touches: an immutable value that joins with `/`, compares, hashes and sorts, and exposes `parent`, `parents`, `name`, `suffix`, `stem` and `parts`. Unlike `pathlib.Path` it has no I/O methods, so a path can never reach the disk on its own; every read and write goes through `E.FileSystem`. Joining follows the standard library's rules: an absolute right-hand side replaces the left, and redundant separators collapse.

```python
import effecton as E

# ---cut---
config = E.Path("/repo") / ".changeset" / "config.toml"
#  ^?
config.parent  # Path('/repo/.changeset')
config.suffix  # '.toml'
```

This repo's ruff config bans `pathlib`, `os.path`, `shutil`, `tempfile` and the `os` file functions outside the FileSystem and Process modules, so all code goes through `E.FileSystem`, `E.Process` and `E.Path`.
