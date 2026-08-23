import frontmatter

import effecton as E
from skills_cli import errors, skill

PLAIN_BODY = "---\nname: my-skill\n---\n\nsome body"


def test_parse_splits_frontmatter_and_content():
    result = E.run_sync(skill.parse(PLAIN_BODY))

    assert isinstance(result, E.Succeeded)
    assert result.value.metadata == {"name": "my-skill"}
    assert result.value.content == "some body"


def test_parse_fails_on_invalid_yaml():
    body = "---\nname: [unclosed\n---\n\nsome body"

    result = E.run_sync(skill.parse(body))

    assert isinstance(result, E.Failure)
    assert isinstance(result.cause, E.Fail)
    assert isinstance(result.cause.error, errors.FrontmatterParseError)


def test_detects_a_disabled_skill():
    post = frontmatter.loads("---\ndisable-model-invocation: true\n---\nbody")

    assert skill.is_model_invocation_disabled(post)


def test_a_false_flag_is_not_disabled():
    post = frontmatter.loads("---\ndisable-model-invocation: false\n---\nbody")

    assert not skill.is_model_invocation_disabled(post)


def test_an_absent_flag_is_not_disabled():
    post = frontmatter.loads(PLAIN_BODY)

    assert not skill.is_model_invocation_disabled(post)


def test_a_truthy_string_flag_is_not_disabled():
    post = frontmatter.loads("---\ndisable-model-invocation: 'true'\n---\nbody")

    assert not skill.is_model_invocation_disabled(post)


def test_disable_model_invocation_sets_the_flag_and_keeps_the_body():
    post = frontmatter.loads(PLAIN_BODY)

    result = E.run_sync(skill.disable_model_invocation(post))

    # dumps re-serializes with sorted keys, so assert containment, not
    # equality.
    assert isinstance(result, E.Succeeded)
    assert "disable-model-invocation: true" in result.value
    assert "name: my-skill" in result.value
    assert "some body" in result.value
