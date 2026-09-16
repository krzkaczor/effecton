---
title: Racing
description: Running two effects against each other and keeping the first outcome while the loser is interrupted.
---

# Racing

`E.race_first(left, right)` returns the first completed outcome, whether success, typed failure, defect, or interruption. It interrupts the loser and awaits its finalizers; loser cleanup cannot replace the winner's outcome. The left wins when both are complete at selection. Cancelling the parent waits for both branches to finish cleanup.

Both branches inherit surrounding requirements, including the Clock, and the result carries the union of their value, error, and requirement types. Racing is async only: synchronous runners report `AsyncEffectInSyncRun`.

```python
from dataclasses import dataclass
from typing import Never, final

import effecton as E


@final
@dataclass(frozen=True)
class FetchError(E.EffectonError):
    pass


def fetch_total() -> E.Effect[int, FetchError]:
    return E.success(1)


def heartbeat_forever() -> E.Effect[Never]:
    return E.sleep(seconds=1).flat_map(lambda _: heartbeat_forever())


# ---cut---
# Stop the heartbeat when the operation completes; a heartbeat failure
# also stops the operation.
program = E.race_first(fetch_total(), heartbeat_forever())
#  ^?
```

Resource lifetime follows the owning scope: use `branch.scoped()` to release that branch's resources before the race returns. Resources acquired into a surrounding scope live until that scope closes. Racing `fiber.join()` interrupts the waiter; the independently forked fiber keeps running.

More examples: [`test_race.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_race.py).
