"""Durations given as a timedelta or as timedelta's keyword parts.

sleep, timeout and the Schedule constructors take either
``timedelta(seconds=5)`` or ``seconds=5`` directly; resolve turns whichever
was given into the timedelta the rest of the library works with.
"""

from datetime import timedelta
from typing import TypedDict


class Parts(TypedDict, total=False):
    """The keyword arguments of timedelta."""

    weeks: float
    days: float
    hours: float
    minutes: float
    seconds: float
    milliseconds: float
    microseconds: float


def resolve(duration: timedelta | None, parts: Parts) -> timedelta:
    """The duration as given, or one built from parts; exactly one of the two."""
    if duration is not None:
        if parts:
            raise TypeError("Give a timedelta or its parts (seconds=...), not both")
        return duration
    if not parts:
        raise TypeError("Give a timedelta or at least one part such as seconds=...")
    return timedelta(**parts)
