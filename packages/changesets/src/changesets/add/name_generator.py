"""Name-generator service: random adjective-noun-verb slugs, like changesets.

Live draws through the implicit E.Random service, so providing
E.Random.Test(seed) makes the generated names reproducible.
"""

import typing
from dataclasses import dataclass, field
from typing import runtime_checkable

import effecton as E

ADJECTIVES = (
    "brave",
    "calm",
    "eager",
    "fuzzy",
    "gentle",
    "happy",
    "lucky",
    "mighty",
    "quiet",
    "shiny",
    "swift",
    "witty",
)

NOUNS = (
    "badgers",
    "candles",
    "dolphins",
    "falcons",
    "islands",
    "lanterns",
    "mangoes",
    "otters",
    "pandas",
    "rivers",
    "tigers",
    "walruses",
)

VERBS = (
    "bounce",
    "cheer",
    "dance",
    "gather",
    "juggle",
    "listen",
    "sparkle",
    "swim",
    "travel",
    "wander",
    "whistle",
    "yawn",
)


@runtime_checkable
class Protocol(typing.Protocol):
    def generate(self) -> E.Effect[str]: ...


class Live(Protocol):
    @E.gen
    def generate(self) -> E.EffectGen[str]:
        rng = yield from E.random()

        adjective = yield from rng.choice(ADJECTIVES)
        noun = yield from rng.choice(NOUNS)
        verb = yield from rng.choice(VERBS)
        return f"{adjective}-{noun}-{verb}"


@dataclass
class Test(Protocol):
    names: list[str] = field(default_factory=lambda: ["happy-pandas-dance"])

    @E.suspend
    def generate(self) -> E.Effect[str]:
        return E.success(self.names.pop(0))
