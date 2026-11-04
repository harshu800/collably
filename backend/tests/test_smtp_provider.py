from __future__ import annotations

from email.message import EmailMessage
from types import SimpleNamespace

import pytest

from app.providers.email import smtp


class FakeSMTP:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.calls: list[tuple[str, object]] = []
        self.message: EmailMessage | None = None

    def __enter__(self) -> FakeSMTP:
        return self

    def __exit__(self, *_args) -> None:
        self.calls.append(("close", None))

    def ehlo(self) -> None:
        self.calls.append(("ehlo", None))

    def starttls(self, *, context) -> None:
        self.calls.append(("starttls", context))

    def login(self, username: str, password: str) -> None:
        self.calls.append(("login", (username, password)))

    def send_message(self, message, *, from_addr, to_addrs) -> None:
        self.message = message
        self.calls.append(("send_message", (from_addr, to_addrs)))


def _settings(**overrides):
    settings = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_from_email": "Collably <notifications@example.com>",
        "smtp_username": "smtp-user",
        "smtp_password": "smtp-password",
    }
    settings.update(overrides)
    return SimpleNamespace(**settings)


def test_smtp_send_uses_starttls_auth_and_multipart(monkeypatch) -> None:
    clients: list[FakeSMTP] = []

    def create_client(*args, **kwargs) -> FakeSMTP:
        client = FakeSMTP(*args, **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(smtp, "get_settings", lambda: _settings())
    monkeypatch.setattr(smtp.smtplib, "SMTP", create_client)

    smtp.SMTPEmailProvider().send(
        to="creator@example.com",
        subject="Campaign update",
        body_text="Your application was accepted.",
        body_html="<p>Your application was accepted.</p>",
    )

    client = clients[0]
    assert client.args == ("smtp.example.com", 587)
    assert client.kwargs["timeout"] == smtp.SMTPEmailProvider.timeout_seconds
    assert [call[0] for call in client.calls] == [
        "ehlo",
        "starttls",
        "ehlo",
        "login",
        "send_message",
        "close",
    ]
    assert client.message is not None
    assert client.message["To"] == "creator@example.com"
    assert client.message["Subject"] == "Campaign update"
    assert client.message.get_body(("plain",)).get_content().strip() == (
        "Your application was accepted."
    )
    assert client.message.get_body(("html",)).get_content().strip() == (
        "<p>Your application was accepted.</p>"
    )
    assert client.calls[3] == ("login", ("smtp-user", "smtp-password"))
    assert client.calls[4] == (
        "send_message",
        ("notifications@example.com", ["creator@example.com"]),
    )


def test_smtp_implicit_tls_on_port_465(monkeypatch) -> None:
    clients: list[FakeSMTP] = []

    def create_client(*args, **kwargs) -> FakeSMTP:
        client = FakeSMTP(*args, **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(
        smtp, "get_settings", lambda: _settings(smtp_port=465)
    )
    monkeypatch.setattr(smtp.smtplib, "SMTP_SSL", create_client)

    smtp.SMTPEmailProvider().send(
        to="creator@example.com",
        subject="Update",
        body_text="Hello",
    )

    client = clients[0]
    assert client.args == ("smtp.example.com", 465)
    assert client.kwargs["timeout"] == smtp.SMTPEmailProvider.timeout_seconds
    assert client.kwargs["context"] is not None
    assert [call[0] for call in client.calls] == [
        "login",
        "send_message",
        "close",
    ]


def test_smtp_rejects_invalid_recipient_before_connecting(monkeypatch) -> None:
    monkeypatch.setattr(smtp, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        smtp.smtplib,
        "SMTP",
        lambda *_args, **_kwargs: pytest.fail("SMTP must not be opened"),
    )

    with pytest.raises(ValueError, match="recipient"):
        smtp.SMTPEmailProvider().send(
            to="invalid-recipient",
            subject="Update",
            body_text="Hello",
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"smtp_host": ""},
        {"smtp_port": None},
        {"smtp_from_email": ""},
        {"smtp_username": ""},
    ],
)
def test_smtp_requires_complete_settings(monkeypatch, overrides) -> None:
    monkeypatch.setattr(smtp, "get_settings", lambda: _settings(**overrides))
    with pytest.raises(RuntimeError):
        smtp.SMTPEmailProvider()
