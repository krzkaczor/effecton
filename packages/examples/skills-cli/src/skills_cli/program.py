"""The whole install flow as one @gen program over the three services."""

from pathlib import Path

import effecton as E
from skills_cli import file_system as FileSystem
from skills_cli import http_client as HttpClient
from skills_cli import parse_url, skill
from skills_cli import terminal as Terminal
from skills_cli.errors import InstallError

type Services = FileSystem.Protocol | HttpClient.Protocol | Terminal.Protocol


@E.gen
def install_skill(url: str, home: Path) -> E.EffectGen[str, InstallError, Services]:
    fs = yield from E.require(FileSystem.Protocol)
    http = yield from E.require(HttpClient.Protocol)
    terminal = yield from E.require(Terminal.Protocol)

    parsed = yield from parse_url.parse(url)
    yield from E.log_info("Getting skill at:", parsed.raw_url)
    body = yield from http.get_text(parsed.raw_url)

    parsed_body = yield from skill.parse(body)
    if not skill.is_model_invocation_disabled(parsed_body):
        convert = yield from terminal.confirm(
            f"Skill {parsed.skill_name} is not a slash command, "
            "should I make it into one?"
        )
        if convert:
            body = yield from skill.disable_model_invocation(parsed_body)

    skill_dir = home / ".agents/skills" / parsed.skill_name
    skill_dir_exists = yield from fs.exists(skill_dir)
    if skill_dir_exists:
        yield from E.log_warning("Skill dir already exists:", skill_dir)
    yield from fs.mkdir(skill_dir)
    yield from fs.write_text(skill_dir / "SKILL.md", body)
    yield from E.log_info("Skill installed into:", skill_dir)

    link = home / ".claude/skills" / parsed.skill_name
    link_exists = yield from fs.exists(link)
    if link_exists:
        yield from E.log_info("Symlink already exists:", link)
    else:
        yield from fs.mkdir(link.parent)
        yield from fs.symlink(link, skill_dir)
        yield from E.log_info("Symlink created:", link)

    return parsed.skill_name
