"""Load .changeset/config.toml: the packages this repo releases."""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import effecton as E


@dataclass(frozen=True)
class MissingConfig(E.EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"Missing changesets config: {self.path}"


@dataclass(frozen=True)
class MalformedConfig(E.EffectonError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"Invalid config {self.path}: {self.reason}"


@dataclass(frozen=True)
class UnknownPackage(E.EffectonError):
    path: Path
    package: str

    def __str__(self) -> str:
        return (
            f"Unknown package {self.package!r} (packages are declared in {self.path})"
        )


type ConfigError = MissingConfig | MalformedConfig


@dataclass(frozen=True)
class Config:
    packages: Mapping[str, Path]


def parse(path: Path, text: str) -> E.Effect[Config, MalformedConfig]:
    def load() -> dict[str, Any]:
        return tomllib.loads(text)

    def to_error(e: Exception) -> MalformedConfig:
        if isinstance(e, tomllib.TOMLDecodeError):
            return MalformedConfig(path=path, reason=str(e))
        raise e

    def validate(data: dict[str, Any]) -> E.Effect[Config, MalformedConfig]:
        packages = data.get("packages")
        if not isinstance(packages, dict) or not packages:
            reason = "the [packages] table is missing or empty"
            return E.fail(MalformedConfig(path=path, reason=reason))
        directories: dict[str, Path] = {}
        for name, directory in packages.items():
            if not isinstance(directory, str):
                reason = f"package {name!r} must map to a directory string"
                return E.fail(MalformedConfig(path=path, reason=reason))
            directories[name] = Path(directory)
        return E.success(Config(packages=directories))

    return E.attempt(load, to_error).flat_map(validate)
