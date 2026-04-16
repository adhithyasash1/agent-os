"""LLM interface.

All backends implement `complete(prompt, system=...)` returning a string.
"""
from __future__ import annotations

from typing import Protocol


class LLM(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...
