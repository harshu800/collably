"""Email provider contract (Protocol)."""

from __future__ import annotations

from typing import Protocol


class EmailProvider(Protocol):
    name: str

    def send(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None:
        ...
