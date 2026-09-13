"""The add flow: write a new changeset file under a generated name."""

import effecton as E
from changesets.add import name_generator as NameGenerator
from changesets.shared import changeset, config, repo
from changesets.shared.semver import Bump

type AddServices = E.FileSystem.Protocol | NameGenerator.Protocol

type AddError = (
    repo.NotAChangesetRepo
    | config.ConfigError
    | config.UnknownPackage
    | E.FileSystem.FileNotFound
    | E.FileSystem.PermissionDenied
    | E.FileSystem.PathIsADirectory
    | E.FileSystem.PathIsNotADirectory
)


@E.gen
def add_changeset(
    start: E.Path, package: str, level: Bump, summary: str
) -> E.EffectGen[E.Path, AddError, AddServices]:
    fs = yield from E.require(E.FileSystem.Protocol)

    root = yield from repo.find_root(start)
    cfg = yield from repo.load_config(root)
    directory = root / repo.CHANGESET_DIR

    if package not in cfg.packages:
        config_path = directory / repo.CONFIG_FILE
        error = config.UnknownPackage(path=config_path, package=package)
        return (yield from E.fail(error))

    name = yield from pick_name(directory)
    path = directory / f"{name}.md"
    content = changeset.serialize({package: level}, summary.strip())
    yield from fs.write_file_string(path, content)
    return path


@E.gen
def pick_name(
    directory: E.Path,
) -> E.EffectGen[str, E.FileSystem.PermissionDenied, AddServices]:
    fs = yield from E.require(E.FileSystem.Protocol)
    name_generator = yield from E.require(NameGenerator.Protocol)

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
