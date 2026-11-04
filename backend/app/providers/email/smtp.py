"""SMTP email provider with mandatory transport encryption."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr

from app.core.config import get_settings


class SMTPEmailProvider:
    name = "smtp"
    timeout_seconds = 10

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.smtp_host or settings.smtp_port is None:
            raise RuntimeError("SMTP_HOST and SMTP_PORT must be configured")
        if not settings.smtp_from_email:
            raise RuntimeError("SMTP_FROM_EMAIL must be configured")
        if bool(settings.smtp_username) != bool(settings.smtp_password):
            raise RuntimeError(
                "SMTP_USERNAME and SMTP_PASSWORD must be configured together"
            )
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._from_email = settings.smtp_from_email
        self._username = settings.smtp_username
        self._password = settings.smtp_password

    def _message(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None,
    ) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self._from_email
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body_text)
        if body_html is not None:
            message.add_alternative(body_html, subtype="html")
        return message

    def send(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None:
        """Send an email using implicit TLS (465) or mandatory STARTTLS."""

        recipient = parseaddr(to)[1]
        if (
            recipient.count("@") != 1
            or recipient.startswith("@")
            or recipient.endswith("@")
        ):
            raise ValueError("SMTP recipient address is invalid")
        message = self._message(
            to=to,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )
        context = ssl.create_default_context()
        if self._port == 465:
            with smtplib.SMTP_SSL(
                self._host,
                self._port,
                timeout=self.timeout_seconds,
                context=context,
            ) as client:
                self._login_and_send(client, message, recipient)
            return

        with smtplib.SMTP(
            self._host,
            self._port,
            timeout=self.timeout_seconds,
        ) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
            self._login_and_send(client, message, recipient)

    def _login_and_send(
        self,
        client: smtplib.SMTP | smtplib.SMTP_SSL,
        message: EmailMessage,
        recipient: str,
    ) -> None:
        if self._username:
            client.login(self._username, self._password)
        client.send_message(
            message,
            from_addr=parseaddr(self._from_email)[1],
            to_addrs=[recipient],
        )
