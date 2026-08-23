from dataclasses import dataclass
from typing import Never, assert_type, final

import effecton as E


@final
@dataclass(frozen=True)
class Greeting(E.ImplicitRequirement):
    text: str

    @classmethod
    def default(cls) -> Greeting:
        return Greeting("hello")


@dataclass(frozen=True)
class Db:
    url: str


# --- require_implicit: R stays Never, so the effect is runnable bare ---

assert_type(E.require_implicit(Greeting), E.Effect[Greeting])
assert_type(E.run_sync(E.require_implicit(Greeting)), E.Succeeded[Greeting] | E.Failure)

# Mixing with a plain requirement: only the plain one enters R.
_mixed = E.require_implicit(Greeting).flat_map(
    lambda g: E.require(Db).map(lambda db: (g, db))
)
assert_type(_mixed, E.Effect[tuple[Greeting, Db], Never, Db])

# An implicit finalizer adds nothing to R; a plain one still does. This
# pins why require_implicit is a separate function: overloads on require
# resolved through the implicit branch here and silently dropped Db.
assert_type(E.success(1).on_exit(E.require_implicit(Greeting)), E.Effect[int])
assert_type(E.success(1).on_exit(E.require(Db)), E.Effect[int, Never, Db])

# --- require_implicit: negative tests ---

# A class without a default() classmethod is not an implicit requirement.
E.require_implicit(Db)  # type: ignore[type-var]


# Explicitly extending the protocol makes a missing default() a static
# error at the point of use: the class stays abstract until implemented.
class _MissingDefault(E.ImplicitRequirement):
    pass


_MissingDefault()  # type: ignore[abstract]


# Plain require on an implicit class still demands provision; the
# default fallback is opt-in through require_implicit.
# Type-checked only; never called.
def _plain_require_is_not_runnable() -> None:
    E.run_sync(E.require(Greeting))  # type: ignore[arg-type]


# --- provide_implicit: preserves all three channels ---

assert_type(
    E.provide_implicit(E.require_implicit(Greeting), Greeting("hi")),
    E.Effect[Greeting],
)
assert_type(
    E.provide_implicit(_mixed, Greeting("hi")), E.Effect[tuple[Greeting, Db], Never, Db]
)

# --- provide_implicit: negative tests ---

# Only implicit-requirement values can be provided this way.
E.provide_implicit(E.success(1), Db("pg"))  # type: ignore[type-var]

# --- RequirementProvider: implicit overrides ride along with plain provisions ---

_runnable = (
    E.RequirementProvider()
    .and_provide(Db)(Db("postgres://x"))
    .and_provide(Greeting)(Greeting("provided"))
    .apply(_mixed)
)
assert_type(_runnable, E.Effect[tuple[Greeting, Db]])
