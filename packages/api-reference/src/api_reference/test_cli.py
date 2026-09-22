import effecton as E
from api_reference import cli


def program(argv: tuple[str, ...], fs: E.FileSystem.Test):
    return (
        E.Cli.run(cli.app)
        .provide(E.Process.Protocol)(E.Process.Test(arguments=argv))
        .provide(E.FileSystem.Protocol)(fs)
    )


def test_generate_writes_the_page(capsys):
    fs = E.FileSystem.Test()

    exit = E.run_sync_exit(program(("--out", "out/api.md"), fs))

    assert exit == E.Succeeded(None)
    assert capsys.readouterr().out == "Wrote out/api.md\n"
    assert E.Path("out/api.md") in fs.files


def test_unknown_option_is_a_usage_error():
    exit = E.run_sync_exit(program(("--nope",), E.FileSystem.Test()))

    assert exit == E.Failure(
        E.Fail(
            E.Cli.UsageError(
                "api-reference",
                "Usage: api-reference [OPTIONS]",
                E.Cli.UnknownOption("--nope"),
            )
        )
    )
