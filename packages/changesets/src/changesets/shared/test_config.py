from pathlib import Path

import effecton as E
from changesets.shared import config
from changesets.shared.config import Config, MalformedConfig

PATH = Path("/repo/.changeset/config.toml")


def test_parses_the_packages_table():
    text = '[packages]\neffecton = "packages/effecton"\nother = "packages/other"\n'

    result = E.run_sync(config.parse(PATH, text))

    assert result == E.Succeeded(
        value=Config(
            packages={
                "effecton": Path("packages/effecton"),
                "other": Path("packages/other"),
            }
        )
    )


def test_rejects_invalid_toml():
    result = E.run_sync(config.parse(PATH, "not toml ["))

    assert isinstance(result, E.Failure)
    assert isinstance(result.cause, E.Fail)
    assert isinstance(result.cause.error, MalformedConfig)
    assert result.cause.error.path == PATH


def test_rejects_a_missing_packages_table():
    result = E.run_sync(config.parse(PATH, "[other]\nkey = 1\n"))

    assert result == E.Failure(
        cause=E.Fail(
            MalformedConfig(
                path=PATH, reason="the [packages] table is missing or empty"
            )
        )
    )


def test_rejects_a_non_string_package_directory():
    result = E.run_sync(config.parse(PATH, "[packages]\neffecton = 1\n"))

    assert result == E.Failure(
        cause=E.Fail(
            MalformedConfig(
                path=PATH, reason="package 'effecton' must map to a directory string"
            )
        )
    )
