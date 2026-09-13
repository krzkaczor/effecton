"""Type-level pins for the Process service. Nothing here runs: ty checks the
function bodies and pytest never calls them."""

from typing import Never, assert_type

import effecton as E


def _reads_are_plain_effects_of_path() -> None:
    process: E.Process.Protocol = E.Process.Live()

    assert_type(process.cwd(), E.Effect[E.Path])
    assert_type(process.home(), E.Effect[E.Path])
    assert_type(
        E.require(E.Process.Protocol),
        E.Effect[E.Process.Protocol, Never, E.Process.Protocol],
    )
    assert_type(
        E.require(E.Process.Protocol)
        .flat_map(lambda p: p.cwd())
        .provide(E.Process.Protocol)(E.Process.Test()),
        E.Effect[E.Path],
    )
    assert_type(E.Process.Test().current_directory, E.Path)


def _process_negative() -> None:
    # Only a Process implementation can be provided as the Process.
    E.require(E.Process.Protocol).provide(E.Process.Protocol)(object())  # ty: ignore[invalid-argument-type]

    # The directories are Paths, not strings.
    E.Process.Test(current_directory="/repo")  # ty: ignore[invalid-argument-type]

    # The requirement must be provided before running.
    E.run_sync(E.require(E.Process.Protocol))  # ty: ignore[invalid-argument-type]

    # Implementations are leaves: neither can be subclassed.
    class CustomLive(E.Process.Live):  # ty: ignore[subclass-of-final-class]
        pass

    class CustomTest(E.Process.Test):  # ty: ignore[subclass-of-final-class]
        pass
