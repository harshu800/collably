"""Console email provider — logs sends at INFO with structured fields.

Verified in tests via log capture only.
"""

from __future__ import annotations

from app.core.logging import get_logger

_log = get_logger("email.console")


class ConsoleEmailProvider:
    name = "console"

    def send(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None:
        _log.info(
            "[EMAIL]",
            to=to,
            subject=subject,
            body_text_len=len(body_text),
            has_html=body_html is not None,
        )
