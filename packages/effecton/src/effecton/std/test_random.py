import random

import pytest

import effecton as E

ITEMS = ["a", "b", "c", "d"]


def test_random_resolves_to_the_live_generator_by_default():
    service = E.run_sync(E.random())

    assert isinstance(service, E.Random.Live)


def test_run_async_resolves_to_the_live_generator_too():
    service = E.run_async(E.random())

    assert isinstance(service, E.Random.Live)


def test_protocol_defaults_to_live():
    assert E.Random.Protocol.default() == E.Random.Live()


def test_live_random_is_in_the_unit_interval():
    draws = [E.run_sync(E.random().flat_map(lambda r: r.random())) for _ in range(50)]

    assert all(0.0 <= draw < 1.0 for draw in draws)


def test_live_uniform_stays_within_the_bounds():
    draws = [
        E.run_sync(E.random().flat_map(lambda r: r.uniform(2.5, 3.5)))
        for _ in range(50)
    ]

    assert all(2.5 <= draw <= 3.5 for draw in draws)


def test_live_randint_stays_within_the_bounds():
    draws = [
        E.run_sync(E.random().flat_map(lambda r: r.randint(1, 6))) for _ in range(50)
    ]

    assert all(1 <= draw <= 6 for draw in draws)
    assert all(isinstance(draw, int) for draw in draws)


def test_live_choice_picks_a_member():
    draws = [
        E.run_sync(E.random().flat_map(lambda r: r.choice(ITEMS))) for _ in range(20)
    ]

    assert all(draw in ITEMS for draw in draws)


def test_live_shuffle_returns_a_permutation_and_leaves_the_input_alone():
    items = list(ITEMS)

    result = E.run_sync(E.random().flat_map(lambda r: r.shuffle(items)))

    assert sorted(result) == sorted(ITEMS)
    assert result is not items
    assert items == ITEMS


def test_test_generator_seed_defaults_to_zero():
    assert E.Random.Test() == E.Random.Test(seed=0)


@pytest.mark.parametrize("seed", [0, 1, 42])
def test_test_generator_repeats_its_draws_for_a_seed(seed: int):
    @E.gen
    def draw_everything() -> E.EffectGen[list[float | str | list[str]]]:
        rng = yield from E.random()

        x = yield from rng.random()
        y = yield from rng.uniform(1, 2)
        z = yield from rng.randint(1, 100)
        c = yield from rng.choice(ITEMS)
        s = yield from rng.shuffle(ITEMS)
        return [x, y, z, c, s]

    def draws(service: E.Random.Test) -> list[float | str | list[str]]:
        provided = draw_everything().provide(E.Random.Protocol)(service)
        return E.run_sync(provided) + E.run_sync(provided)

    first = draws(E.Random.Test(seed))
    second = draws(E.Random.Test(seed))

    assert first == second


def test_test_generator_matches_the_stdlib_generator_with_that_seed():
    service = E.Random.Test(seed=7)
    expected = random.Random(7)
    program = E.random().flat_map(lambda r: r.uniform(0.8, 1.2))

    draws = [E.run_sync(program.provide(E.Random.Protocol)(service)) for _ in range(5)]

    assert draws == [expected.uniform(0.8, 1.2) for _ in range(5)]


def test_test_generators_with_different_seeds_differ():
    program = E.random().flat_map(lambda r: r.random())

    first = E.run_sync(program.provide(E.Random.Protocol)(E.Random.Test(seed=1)))
    second = E.run_sync(program.provide(E.Random.Protocol)(E.Random.Test(seed=2)))

    assert first != second


def test_test_shuffle_leaves_the_input_alone():
    items = list(ITEMS)
    program = E.random().flat_map(lambda r: r.shuffle(items))

    result = E.run_sync(program.provide(E.Random.Protocol)(E.Random.Test()))

    assert sorted(result) == sorted(ITEMS)
    assert items == ITEMS


def test_override_is_scoped_to_the_wrapped_effect():
    overridden = E.random().provide(E.Random.Protocol)(E.Random.Test())
    after = overridden.flat_map(
        lambda inner: E.random().map(lambda outer: (inner, outer))
    )

    inner, outer = E.run_sync(after)

    assert isinstance(inner, E.Random.Test)
    assert isinstance(outer, E.Random.Live)


@E.gen
def test_the_test_random_fixture_is_provided(
    test_random: E.Random.Test,
) -> E.EffectGen[None]:
    service = yield from E.random()
    draw = yield from service.random()

    assert service is test_random
    assert draw == random.Random(0).random()
