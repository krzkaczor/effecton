"""Changeset-based changelog and version management, built on effecton.

Each CLI command owns a directory (``add/``, ``status/``, ``version/``,
``notes/``) holding its Typer entry point and ``@gen`` program; building
blocks used by several commands live in ``shared/``. Services follow the
module-as-namespace pattern: a service module exports Protocol / Live /
Test and consumers alias it —
``from changesets.shared import file_system as FileSystem``.
"""

from changesets import add, notes, shared, status, version

__all__ = ["add", "notes", "shared", "status", "version"]
