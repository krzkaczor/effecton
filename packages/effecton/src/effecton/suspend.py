"""Lazily defer effect construction.

``suspend`` has two forms, resolved by the callable's signature. The
thunk form, ``suspend(thunk)``, returns an ``Effect`` that rebuilds the
thunk's effect on every interpretation. The decorator form, ``@suspend``
on a function that takes arguments, wraps it so each call captures its
arguments and defers the body the same way: it runs only when the
returned effect is interpreted. A zero-argument function resolves to the
thunk form, so decorating one yields the effect itself.
"""

from collections.abc import Callable
from functools import wraps
from inspect import signature
from typing import Any, overload

from effecton.effect import Effect, EffectonError, sync


@overload
def suspend[A, E: EffectonError, R](
    f: Callable[[], Effect[A, E, R]],
) -> Effect[A, E, R]: ...


@overload
def suspend[**P, A, E: EffectonError, R](
    f: Callable[P, Effect[A, E, R]],
) -> Callable[P, Effect[A, E, R]]: ...


def suspend(f: Callable[..., Effect[Any, Any, Any]]) -> Any:
    def defer(thunk: Callable[[], Effect[Any, Any, Any]]) -> Effect[Any, Any, Any]:
        return sync(thunk).flat_map(lambda x: x)

    # bind() succeeds exactly when f is callable with no arguments, which
    # mirrors the static dispatch: such callables match the thunk overload.
    try:
        signature(f).bind()
    except TypeError:

        @wraps(f)
        def wrapper(*args: object, **kwargs: object) -> Effect[Any, Any, Any]:
            return defer(lambda: f(*args, **kwargs))

        return wrapper
    return defer(f)
