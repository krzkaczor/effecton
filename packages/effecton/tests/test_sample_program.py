from dataclasses import dataclass

import effecton as E


@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str
    pass


@dataclass(frozen=True)
class NegativeIntError(E.EffectonError):
    value: int
    pass


def parse(s: str) -> E.Effect[int, ParseError]:
    try:
        return E.success(int(s))
    except ValueError:
        return E.fail(ParseError(s))


def program(s: str) -> E.Effect[int, ParseError | NegativeIntError]:
    return (
        parse(s)
        .map(lambda x: x * 2)
        .flat_map(lambda x: E.success(x) if x > 0 else E.fail(NegativeIntError(x)))
    )


def test_sample_program_succeded():
    assert E.run_sync(program("21")) == E.Succeeded(value=42)


def test_sample_program_failure_negative_number():
    assert E.run_sync(program("-5")) == E.Failure(cause=E.Fail(NegativeIntError(-10)))


def test_sample_program_failure_parse():
    assert E.run_sync(program("abc5")) == E.Failure(cause=E.Fail(ParseError("abc5")))


def test_sample_program_failure_catch():
    def catch(error: NegativeIntError | ParseError) -> E.Effect[int, ParseError]:
        match error:
            case NegativeIntError():
                return E.success(0)
            case _:
                return E.fail(error)

    p = program("-5").catch_all(catch)

    assert E.run_sync(p) == E.Succeeded(0)


def test_sample_program_failure_catch2():
    p = program("-5").catch_all(
        lambda e: E.success(0) if isinstance(e, NegativeIntError) else E.fail(e)
    )

    assert E.run_sync(p) == E.Succeeded(0)
