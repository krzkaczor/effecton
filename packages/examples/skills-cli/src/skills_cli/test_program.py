import effecton as E
from skills_cli import parse_url
from skills_cli import terminal as Terminal
from skills_cli.program import InstallError, install_skill

HOME = E.Path("/home/user")
URL = "https://github.com/octo/my-skill/blob/main/SKILL.md"
RAW_URL = "https://raw.githubusercontent.com/octo/my-skill/main/SKILL.md"
SKILL_DIR = HOME / ".agents/skills/my-skill"
LINK = HOME / ".claude/skills/my-skill"
SLASH_CMD_BODY = "---\ndisable-model-invocation: true\n---\n\nsome body"
PLAIN_BODY = "---\nname: my-skill\n---\n\nsome body"


def capture() -> tuple[list[E.LogData], E.CurrentLoggers]:
    entries: list[E.LogData] = []
    return entries, E.CurrentLoggers((E.EffectonLogger(log=entries.append),))


def wire(
    fs: E.FileSystem.Test,
    http: E.HttpClient.Test,
    terminal: Terminal.Test,
    url: str = URL,
) -> tuple[list[E.LogData], E.Effect[str, InstallError]]:
    provided = (
        install_skill(url, HOME)
        .provide(E.FileSystem.Protocol)(fs)
        .provide(E.HttpClient.Protocol)(http)
        .provide(Terminal.Protocol)(terminal)
    )
    entries, loggers = capture()
    return entries, E.provide_implicit(provided, loggers)


def test_installs_an_already_slash_command_skill_without_prompting():
    fs = E.FileSystem.Test()
    http = E.HttpClient.Test(responses={RAW_URL: SLASH_CMD_BODY})
    terminal = Terminal.Test()
    entries, program = wire(fs, http, terminal)

    result = E.run_sync_exit(program)

    assert result == E.Succeeded(value="my-skill")
    assert terminal.prompts == []
    assert fs.files == {SKILL_DIR / "SKILL.md": SLASH_CMD_BODY}
    assert fs.links == {LINK: SKILL_DIR}
    assert SKILL_DIR in fs.directories
    assert [e.message for e in entries] == [
        ("Getting skill at:", RAW_URL),
        ("Skill installed into:", SKILL_DIR),
        ("Symlink created:", LINK),
    ]


def test_converts_to_a_slash_command_when_confirmed():
    fs = E.FileSystem.Test()
    http = E.HttpClient.Test(responses={RAW_URL: PLAIN_BODY})
    terminal = Terminal.Test(answer=True)
    _, program = wire(fs, http, terminal)

    result = E.run_sync_exit(program)

    assert result == E.Succeeded(value="my-skill")
    assert terminal.prompts == [
        "Skill my-skill is not a slash command, should I make it into one?"
    ]
    written = E.run_sync(fs.read_file_string(SKILL_DIR / "SKILL.md"))
    assert "disable-model-invocation: true" in written
    assert "some body" in written


def test_keeps_the_body_verbatim_when_conversion_is_declined():
    fs = E.FileSystem.Test()
    http = E.HttpClient.Test(responses={RAW_URL: PLAIN_BODY})
    terminal = Terminal.Test(answer=False)
    _, program = wire(fs, http, terminal)

    result = E.run_sync_exit(program)

    assert result == E.Succeeded(value="my-skill")
    assert fs.files == {SKILL_DIR / "SKILL.md": PLAIN_BODY}


def test_warns_when_the_skill_dir_already_exists():
    fs = E.FileSystem.Test(directories={SKILL_DIR})
    http = E.HttpClient.Test(responses={RAW_URL: SLASH_CMD_BODY})
    entries, program = wire(fs, http, Terminal.Test())

    result = E.run_sync_exit(program)

    assert result == E.Succeeded(value="my-skill")
    assert ("Skill dir already exists:", SKILL_DIR) in [
        e.message for e in entries if e.log_level == E.LogLevel.WARN
    ]


def test_skips_an_already_existing_symlink():
    existing_target = E.Path("/elsewhere")
    fs = E.FileSystem.Test(links={LINK: existing_target})
    http = E.HttpClient.Test(responses={RAW_URL: SLASH_CMD_BODY})
    entries, program = wire(fs, http, Terminal.Test())

    result = E.run_sync_exit(program)

    assert result == E.Succeeded(value="my-skill")
    assert fs.links == {LINK: existing_target}
    assert ("Symlink already exists:", LINK) in [e.message for e in entries]


def test_an_invalid_url_fails_before_touching_anything():
    fs = E.FileSystem.Test()
    http = E.HttpClient.Test()
    terminal = Terminal.Test()
    url = "https://gitlab.com/octo/my-skill/blob/main/SKILL.md"
    _, program = wire(fs, http, terminal, url=url)

    result = E.run_sync_exit(program)

    assert result == E.Failure(
        cause=E.Fail(parse_url.UnsupportedHost(url=url, host="gitlab.com"))
    )
    assert fs.files == {}
    assert fs.links == {}
    assert terminal.prompts == []


def test_an_http_failure_propagates():
    fs = E.FileSystem.Test()
    _, program = wire(fs, E.HttpClient.Test(), Terminal.Test())

    result = E.run_sync_exit(program)

    assert result == E.Failure(
        cause=E.Fail(E.HttpClient.StatusError(method="GET", url=RAW_URL, status=404))
    )
    assert fs.files == {}
