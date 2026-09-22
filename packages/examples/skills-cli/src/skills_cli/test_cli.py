import effecton as E
from skills_cli import cli, parse_url
from skills_cli import terminal as Terminal

SKILL_URL = "https://github.com/octo/my-skill/blob/main/SKILL.md"
RAW_URL = "https://raw.githubusercontent.com/octo/my-skill/main/SKILL.md"


def program(argv: tuple[str, ...], fs: E.FileSystem.Test, http: E.HttpClient.Test):
    return (
        E.Cli.run(cli.app)
        .provide(E.Process.Protocol)(
            E.Process.Test(home_directory=E.Path("/home/me"), arguments=argv)
        )
        .provide(E.FileSystem.Protocol)(fs)
        .provide(E.HttpClient.Protocol)(http)
        .provide(Terminal.Protocol)(Terminal.Test())
    )


def test_install_success(capsys):
    fs = E.FileSystem.Test()
    body = "---\ndisable-model-invocation: true\n---\n\nbody"
    http = E.HttpClient.Test(responses={RAW_URL: body})

    exit = E.run_sync_exit(program((SKILL_URL,), fs, http))

    assert exit == E.Succeeded(None)
    assert capsys.readouterr().out == "Skill my-skill installed.\n"
    assert E.Path("/home/me/.agents/skills/my-skill/SKILL.md") in fs.files


def test_install_failure(capsys):
    exit = E.run_sync_exit(
        program(("not-a-url",), E.FileSystem.Test(), E.HttpClient.Test())
    )

    assert exit == E.Failure(
        E.Fail(parse_url.UnsupportedHost(url="not-a-url", host=""))
    )
    assert capsys.readouterr().out == ""


def test_missing_url_is_a_usage_error():
    exit = E.run_sync_exit(program((), E.FileSystem.Test(), E.HttpClient.Test()))

    assert exit == E.Failure(
        E.Fail(
            E.Cli.UsageError(
                "skills-cli",
                "Usage: skills-cli [OPTIONS] SKILL_URL",
                E.Cli.InvalidArguments((E.Schema.MissingKey(("SKILL_URL",)),)),
            )
        )
    )
