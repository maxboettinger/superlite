"""Shared data types for the guard modules (T0 stub: fields only)."""
from dataclasses import dataclass


@dataclass
class Redirect:  # O(1)
    op: str  # O(1)
    target: str  # O(1)


@dataclass
class Segment:  # O(1)
    words: list[str]  # O(1)
    dyn: list[bool]  # O(1)
    redirects: list[Redirect]  # O(1)
    heredocs: list[str]  # O(1)
    bodies: list[str]  # O(1)
    subshell: str | None  # O(1)
    sep: str  # O(1)
