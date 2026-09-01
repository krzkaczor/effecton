"""The add flow: write a new changeset file under a generated name."""

from pathlib import Path

import effecton as E
from changesets.add import name_generator as NameGenerator
from changesets.shared import changeset, config, repo
from changesets.shared import file_system as FileSystem
from changesets.shared.semver import Bump

type AddServices = FileSystem.Protocol | NameGenerator.Protocol

type AddError = (
    repo.NotAChangesetRepo
    | config.ConfigError
    | config.UnknownPackage
    | FileSystem.FileSystemError
)


@E.gen
def add_changeset(
    start: Path, package: str, level: Bump, summary: str
) -> E.EffectGen[Path, AddError, AddServices]:
    fs = yield from E.require(FileSystem.Protocol)
    name_generator = yield from E.require(NameGenerator.Protocol)

    root = yield from repo.find_root(start)
    cfg = yield from repo.load_config(root)
    directory = root / repo.CHANGESET_DIR

    if package not in cfg.packages:
        config_path = directory / repo.CONFIG_FILE
        error = config.UnknownPackage(path=config_path, package=package)
        return (yield from E.fail(error))

    @E.gen
    def pick_name() -> E.EffectGen[str, FileSystem.PermissionDenied]:
        for _ in range(5):
            candidate = yield from name_generator.generate()
            taken = yield from fs.exists(directory / f"{candidate}.md")
            if not taken:
                return candidate
        base = yield from name_generator.generate()
        index = 2
        while True:
            candidate = f"{base}-{index}"
            taken = yield from fs.exists(directory / f"{candidate}.md")
            if not taken:
                return candidate
            index += 1

    name = yield from pick_name()
    path = directory / f"{name}.md"
    content = changeset.serialize({package: level}, summary.strip())
    yield from fs.write_text(path, content)
    return path
