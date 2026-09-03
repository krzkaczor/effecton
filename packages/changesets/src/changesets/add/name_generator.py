"""Name-generator service: random adjective-noun-verb slugs, like changesets."""

import random
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
    def generate(self) -> E.Effect[str]:
        def go() -> str:
            parts = (
                random.choice(ADJECTIVES),
                random.choice(NOUNS),
                random.choice(VERBS),
            )
            return "-".join(parts)

        return E.sync(go)


@dataclass
class Test(Protocol):
    __test__ = False

    names: list[str] = field(default_factory=lambda: ["happy-pandas-dance"])

    @E.suspend
    def generate(self) -> E.Effect[str]:
        return E.success(self.names.pop(0))
