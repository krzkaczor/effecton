"""Inspect and rewrite a skill's YAML frontmatter."""

import frontmatter
import yaml

import effecton as E
from skills_cli.errors import FrontmatterParseError


def _to_error(e: Exception) -> FrontmatterParseError:
    if isinstance(e, yaml.YAMLError):
        return FrontmatterParseError(message=str(e))
    raise e


def parse(body: str) -> E.Effect[frontmatter.Post, FrontmatterParseError]:
    return E.attempt(lambda: frontmatter.loads(body), _to_error)


def is_model_invocation_disabled(post: frontmatter.Post) -> bool:
    return post.get("disable-model-invocation") is True


def disable_model_invocation(
    post: frontmatter.Post,
) -> E.Effect[str, FrontmatterParseError]:
    def go() -> str:
        post["disable-model-invocation"] = True
        return frontmatter.dumps(post)

    return E.attempt(go, _to_error)
