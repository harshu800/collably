"""Email provider factory. Reads ``settings.email_provider``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.providers.email.base import EmailProvider
from app.providers.email.console import ConsoleEmailProvider

if TYPE_CHECKING:  # pragma: no cover
    from app.core.config import Settings


def get_email_provider(settings: Settings) -> EmailProvider:
    name = settings.email_provider
    if name == "smtp":
        from app.providers.email.smtp import SMTPEmailProvider

        return SMTPEmailProvider()
    return ConsoleEmailProvider()


__all__ = [
    "ConsoleEmailProvider",
    "EmailProvider",
    "get_email_provider",
]
