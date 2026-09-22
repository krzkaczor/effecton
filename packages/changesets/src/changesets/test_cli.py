import subprocess
import sys


def test_status_success(tmp_path):
    changesets = tmp_path / ".changeset"
    changesets.mkdir()
    (changesets / "config.toml").write_text('[packages]\ndemo = "."\n')
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
    )

    result = subprocess.run(
        [sys.executable, "-m", "changesets", "status"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert result.stdout == "No unreleased changesets found.\n"
    assert result.stderr == ""


def test_status_fails_outside_a_changeset_repository(tmp_path):
    # Leave the temporary directory empty: there is no .changeset repository.

    result = subprocess.run(
        [sys.executable, "-m", "changesets", "status"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "ERROR" in result.stderr
    assert "Traceback" not in result.stderr
    assert f"No .changeset directory found in {tmp_path} or any parent" in result.stderr


def test_add_without_a_package_is_a_usage_error(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "changesets",
            "add",
            "--bump",
            "patch",
            "--message",
            "m",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "Missing option '--package'." in result.stderr
    assert "Try 'changeset add --help' for help." in result.stderr


def test_help_exits_zero(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "changesets", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert result.stdout.startswith("Usage: changeset [OPTIONS] COMMAND [ARGS]...\n")
    assert "  add      Create a changeset" in result.stdout
