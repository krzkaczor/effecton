from datetime import datetime, timedelta
from typing import assert_type

import effecton as E

# --- now and sleep: implicit reads, so R stays Never and the effects run bare ---

assert_type(E.now(), E.Effect[datetime])
assert_type(E.run_sync(E.now()), datetime)
assert_type(E.sleep(timedelta(seconds=1)), E.Effect[None])
assert_type(E.require_implicit(E.Clock.Protocol), E.Effect[E.Clock.Protocol])


# Type-checked only; never called, so collecting this module does not sleep.
def _sleep_pins() -> None:
    assert_type(E.run_sync(E.sleep(timedelta(seconds=1))), None)
    assert_type(E.run_async(E.sleep(timedelta(seconds=1))), None)


# --- provide: any implementation overrides the runner's live clock ---

assert_type(E.now().provide(E.Clock.Protocol)(E.Clock.Test()), E.Effect[datetime])
assert_type(E.now().provide(E.Clock.Protocol)(E.Clock.SyncLive()), E.Effect[datetime])
assert_type(E.now().provide(E.Clock.Protocol)(E.Clock.AsyncLive()), E.Effect[datetime])
assert_type(
    E.sleep(timedelta(seconds=1)).provide(E.Clock.Protocol)(E.Clock.Test()),
    E.Effect[None],
)

# --- negative tests ---

# Only a Clock implementation can be provided as the Clock.
E.now().provide(E.Clock.Protocol)(object())  # ty: ignore[invalid-argument-type]

# The duration is a timedelta, not a number of seconds.
E.sleep(1)  # ty: ignore[invalid-argument-type]
