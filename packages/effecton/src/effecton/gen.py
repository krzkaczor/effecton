import functools
from collections.abc import Callable, Generator
from typing import Any, Never, cast

from effecton.effect import Effect, EffectonError, success
from effecton.suspend import suspend

type EffectGen[A, E: EffectonError = Never, R = Never] = Generator[
    Effect[Any, E, R], Any, A
]
"""Return type for @gen generator functions: yields effects, returns A."""


def gen[**P, A2, E2: EffectonError, R2](
    f: Callable[P, EffectGen[A2, E2, R2]],
) -> Callable[P, Effect[A2, E2, R2]]:
    """Turn a generator function into a factory of effects.

    The interpreter runs each yielded effect and sends its result back;
    the generator's return value becomes the effect's success value.
    Use ``x = yield from effect`` instead of ``x = yield effect`` so the
    type of ``x`` is inferred correctly.
    The error and requirement channels flow from the annotated yield type
    either way.

    Each run creates a fresh generator, so the returned effect is a
    reusable value. A failing yielded effect abandons the generator:
    ``try/except`` around a ``yield`` never observes effect failures (use
    catch_all), and ``finally`` blocks run only when the abandoned
    generator is garbage collected.
    """

    @functools.wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Effect[A2, E2, R2]:
        return suspend(lambda: _step(f(*args, **kwargs), None))

    return wrapper


def _step[A2, E2: EffectonError, R2](
    g: EffectGen[A2, E2, R2], to_send: object
) -> Effect[A2, E2, R2]:
    try:
        yielded = g.send(to_send)
    except StopIteration as e:
        return cast("Effect[A2, E2, R2]", success(e.value))
    return yielded.flat_map(lambda v: _step(g, v))
