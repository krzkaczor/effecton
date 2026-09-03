"""Run a fully-provided effect and render its Exit for the terminal."""

from typing import Never

import typer

import effecton as E


def execute[A](runnable: E.Effect[A, E.EffectonError]) -> A:
    match E.run_sync(runnable):
        case E.Succeeded(value=value):
            return value
        case E.Failure(cause=cause):
            return _render_failure(cause)


def _render_failure(cause: E.Cause[E.EffectonError]) -> Never:
    match cause:
        case E.Fail(error=error):
            typer.echo(str(error), err=True)
            raise typer.Exit(code=1)
        case E.Die(defect=defect):
            if isinstance(defect, BaseException):
                raise defect
            raise RuntimeError(str(defect))
