import effecton as E
from skills_cli import parse_url


def test_converts_a_blob_url_at_the_repo_root():
    url = "https://github.com/octo/my-skill/blob/main/SKILL.md"

    result = E.run_sync(parse_url.parse(url))

    assert result == E.Succeeded(
        parse_url.ParsedSkillUrl(
            raw_url="https://raw.githubusercontent.com/octo/my-skill/main/SKILL.md",
            skill_name="my-skill",
        )
    )


def test_names_a_nested_skill_after_its_containing_directory():
    url = "https://github.com/octo/skills/blob/main/deep/writing/SKILL.md"

    result = E.run_sync(parse_url.parse(url))

    assert result == E.Succeeded(
        parse_url.ParsedSkillUrl(
            raw_url=(
                "https://raw.githubusercontent.com/octo/skills/main/"
                "deep/writing/SKILL.md"
            ),
            skill_name="writing",
        )
    )


def test_accepts_the_www_host():
    url = "https://www.github.com/octo/my-skill/blob/main/SKILL.md"

    result = E.run_sync(parse_url.parse(url))

    assert result == E.Succeeded(
        parse_url.ParsedSkillUrl(
            raw_url="https://raw.githubusercontent.com/octo/my-skill/main/SKILL.md",
            skill_name="my-skill",
        )
    )


def test_passes_a_raw_refs_heads_url_through_unchanged():
    url = (
        "https://raw.githubusercontent.com/octo/skills/refs/heads/main/writing/SKILL.md"
    )

    result = E.run_sync(parse_url.parse(url))

    assert result == E.Succeeded(
        parse_url.ParsedSkillUrl(raw_url=url, skill_name="writing")
    )


def test_passes_a_short_raw_url_through_unchanged():
    url = "https://raw.githubusercontent.com/octo/my-skill/main/SKILL.md"

    result = E.run_sync(parse_url.parse(url))

    assert result == E.Succeeded(
        parse_url.ParsedSkillUrl(raw_url=url, skill_name="my-skill")
    )


def test_accepts_a_lowercase_skill_md_filename():
    url = "https://github.com/octo/my-skill/blob/main/skill.md"

    result = E.run_sync(parse_url.parse(url))

    assert isinstance(result, E.Succeeded)
    assert result.value.skill_name == "my-skill"


def test_rejects_an_unsupported_host():
    url = "https://gitlab.com/octo/my-skill/blob/main/SKILL.md"

    result = E.run_sync(parse_url.parse(url))

    assert result == E.Failure(
        cause=E.Fail(parse_url.UnsupportedHost(url=url, host="gitlab.com"))
    )


def test_rejects_a_url_not_pointing_at_skill_md():
    url = "https://github.com/octo/my-skill/blob/main/README.md"

    result = E.run_sync(parse_url.parse(url))

    assert result == E.Failure(cause=E.Fail(parse_url.NotASkillFile(url=url)))


def test_rejects_a_github_url_without_a_blob_segment():
    url = "https://github.com/octo/my-skill/SKILL.md"

    result = E.run_sync(parse_url.parse(url))

    assert result == E.Failure(
        cause=E.Fail(
            parse_url.MalformedSkillPath(
                url=url, reason="expected /owner/repo/blob/ref/path"
            )
        )
    )


def test_rejects_a_too_short_raw_url():
    url = "https://raw.githubusercontent.com/octo/SKILL.md"

    result = E.run_sync(parse_url.parse(url))

    assert result == E.Failure(
        cause=E.Fail(
            parse_url.MalformedSkillPath(
                url=url, reason="expected /owner/repo/[refs/heads/]ref/path"
            )
        )
    )
