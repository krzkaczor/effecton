"""Type-level pins for the Random service. Nothing here runs: ty checks the
function bodies and pytest never calls them."""

from typing import assert_type

import effecton as E


def _random_is_an_implicit_read_so_r_stays_never() -> None:
    assert_type(E.random(), E.Effect[E.Random.Protocol])
    assert_type(E.run_sync(E.random()), E.Random.Protocol)
    assert_type(E.require_implicit(E.Random.Protocol), E.Effect[E.Random.Protocol])
    assert_type(E.random().flat_map(lambda r: r.random()), E.Effect[float])
    assert_type(E.random().flat_map(lambda r: r.uniform(1, 2.5)), E.Effect[float])
    assert_type(E.random().flat_map(lambda r: r.randint(1, 6)), E.Effect[int])


def _choice_and_shuffle_keep_the_element_type() -> None:
    names = ["a", "b"]
    numbers = [1, 2]

    assert_type(E.random().flat_map(lambda r: r.choice(names)), E.Effect[str])
    assert_type(E.random().flat_map(lambda r: r.shuffle(names)), E.Effect[list[str]])
    assert_type(E.random().flat_map(lambda r: r.choice(numbers)), E.Effect[int])
    assert_type(E.random().flat_map(lambda r: r.choice("ab")), E.Effect[str])


def _provide_any_implementation_overrides_the_default() -> None:
    assert_type(
        E.random().provide(E.Random.Protocol)(E.Random.Test(seed=1)),
        E.Effect[E.Random.Protocol],
    )
    assert_type(
        E.random().provide(E.Random.Protocol)(E.Random.Live()),
        E.Effect[E.Random.Protocol],
    )


def _random_negative() -> None:
    # Only a Random implementation can be provided as the Random.
    E.random().provide(E.Random.Protocol)(object())  # ty: ignore[invalid-argument-type]

    # randint takes ints, not floats.
    E.random().flat_map(lambda r: r.randint(1.5, 2))  # ty: ignore[invalid-argument-type]

    # The seed is an int.
    E.Random.Test(seed="1")  # ty: ignore[invalid-argument-type]

    # Implementations are leaves: neither can be subclassed.
    class CustomLive(E.Random.Live):  # ty: ignore[subclass-of-final-class]
        pass

    class CustomTest(E.Random.Test):  # ty: ignore[subclass-of-final-class]
        pass
