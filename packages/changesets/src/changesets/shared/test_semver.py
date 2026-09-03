import effecton as E
from changesets.shared import semver
from changesets.shared.semver import InvalidVersion, Version


def test_parses_a_strict_version():
    result = E.run_sync(semver.parse("effecton", "1.22.333"))

    assert result == E.Succeeded(value=Version(major=1, minor=22, patch=333))


def test_rejects_anything_but_x_y_z():
    for value in ["1.2", "1.2.3.4", "v1.2.3", "1.2.3-rc.1", "", "one.two.three"]:
        result = E.run_sync(semver.parse("effecton", value))

        assert result == E.Failure(
            cause=E.Fail(InvalidVersion(package="effecton", value=value))
        )


def test_bumps_each_level():
    version = Version(major=1, minor=2, patch=3)

    assert semver.bump(version, "major") == Version(major=2, minor=0, patch=0)
    assert semver.bump(version, "minor") == Version(major=1, minor=3, patch=0)
    assert semver.bump(version, "patch") == Version(major=1, minor=2, patch=4)


def test_major_bumps_zero_versions_to_one():
    version = Version(major=0, minor=1, patch=0)

    assert semver.bump(version, "major") == Version(major=1, minor=0, patch=0)


def test_max_bump_picks_the_strongest_level():
    assert semver.max_bump(["patch"]) == "patch"
    assert semver.max_bump(["patch", "minor", "patch"]) == "minor"
    assert semver.max_bump(["patch", "major", "minor"]) == "major"


def test_version_renders_as_dotted_string():
    assert str(Version(major=1, minor=2, patch=3)) == "1.2.3"
