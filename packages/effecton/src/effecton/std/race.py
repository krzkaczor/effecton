from effecton.effect import Effect, EffectonError, RaceFirst


def race_first[A, E: EffectonError, R, B, E2: EffectonError, R2](
    left: Effect[A, E, R], right: Effect[B, E2, R2]
) -> Effect[A | B, E | E2, R | R2]:
    """Return the first completed outcome, interrupting and awaiting the loser.

    Both branches inherit surrounding requirements and start when the race
    runs. Failure, defects, and interruption can win; the left wins when
    both are complete at selection. Loser cleanup cannot replace the winner.
    Parent cancellation waits for both branches' finalizers. Async only.

    Racing Fiber.join() cancels only the waiter, not the independent fiber.
    """
    return RaceFirst[A | B, E | E2, R | R2](left, right)
