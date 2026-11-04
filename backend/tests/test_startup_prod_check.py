"""Startup production-check tests.

These do not need the HTTP app — they construct a :class:`Settings`
instance with the bad combination and call :meth:`validate_production`
directly. The provider guard is parameterised on
:meth:`PaymentProvider.is_implemented` so a future real adapter does not need
a code edit to :mod:`app.core.config` to pass.
"""

from __future__ import annotations

import base64

import pytest

from app.core.config import Settings


def _prod_settings(**overrides) -> Settings:
    """Return a Settings instance pre-populated with safe prod defaults."""

    defaults = dict(
        env="prod",
        debug=False,
        clerk_secret_key="sk_live_abc",
        clerk_publishable_key="pk_live_abc",
        clerk_webhook_secret="whsec_abc",
        clerk_jwks_url="https://app.example.com/.well-known/jwks.json",
        clerk_issuer="https://app.example.com",
        app_base_url="https://api.example.com",
        frontend_base_url="https://app.example.com",
        file_token_secret="prod-grade-file-token-secret-" + ("a" * 16),
        testing_bypass_clerk=False,
        testing_clerk_local_secret="",
        cors_origins="https://app.example.com",
        email_provider="smtp",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_from_email="notifications@example.com",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
        enable_mock_payment_endpoints=False,
        payout_field_enc_key=base64.b64encode(b"\x11" * 32).decode(),
        payment_provider="mock",
        storage_provider="s3",
        s3_bucket="private-test-bucket",
        s3_region="ap-south-1",
    )
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def test_prod_defaults_pass() -> None:
    _prod_settings().validate_production()


def test_prod_debug_true_raises() -> None:
    with pytest.raises(RuntimeError, match="DEBUG"):
        _prod_settings(debug=True).validate_production()


def test_prod_console_email_provider_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="EMAIL_PROVIDER"):
        _prod_settings(email_provider="console").validate_production()


def test_prod_smtp_requires_host_port_and_sender() -> None:
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        _prod_settings(smtp_host="", smtp_port=None, smtp_from_email="").validate_production()


def test_prod_smtp_credentials_must_be_a_pair() -> None:
    with pytest.raises(RuntimeError, match="SMTP_USERNAME"):
        _prod_settings(smtp_password="").validate_production()


def test_prod_smtp_rejects_header_injection_in_sender() -> None:
    with pytest.raises(RuntimeError, match="SMTP_FROM_EMAIL"):
        _prod_settings(
            smtp_from_email="notifications@example.com\r\nBcc: victim@example.com"
        ).validate_production()


# --- CORS / mock endpoints (unchanged) --------------------------------------


def test_prod_cors_wildcard_raises() -> None:
    with pytest.raises(RuntimeError, match="CORS"):
        _prod_settings(cors_origins="*").validate_production()


def test_prod_cors_wildcard_in_list_raises() -> None:
    with pytest.raises(RuntimeError, match="CORS"):
        _prod_settings(cors_origins="https://app.example.com,*").validate_production()


@pytest.mark.parametrize(
    "cors_origins",
    [
        "",
        "http://app.example.com",
        "https://localhost",
        "https://127.0.0.1",
        "https://app.example.com/path",
        "https://app.example.com?query=1",
    ],
)
def test_prod_requires_https_origins_only(cors_origins: str) -> None:
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        _prod_settings(cors_origins=cors_origins).validate_production()


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("app_base_url", "http://api.example.com"),
        ("app_base_url", "https://localhost"),
        ("frontend_base_url", "http://app.example.com"),
        ("clerk_jwks_url", "http://app.example.com/.well-known/jwks.json"),
        ("clerk_issuer", "http://app.example.com"),
    ],
)
def test_prod_requires_https_service_urls(setting: str, value: str) -> None:
    with pytest.raises(RuntimeError, match=setting.upper()):
        _prod_settings(**{setting: value}).validate_production()


def test_prod_mock_endpoints_enabled_raises() -> None:
    with pytest.raises(RuntimeError, match="MOCK"):
        _prod_settings(enable_mock_payment_endpoints=True).validate_production()


# --- Clerk configuration ---------------------------------------------------


def test_prod_placeholder_clerk_secret_key_raises() -> None:
    with pytest.raises(RuntimeError, match="CLERK_SECRET_KEY"):
        _prod_settings(clerk_secret_key="sk_test_REPLACE_ME").validate_production()


def test_prod_rejects_non_live_clerk_secret_key() -> None:
    with pytest.raises(RuntimeError, match="CLERK_SECRET_KEY"):
        _prod_settings(clerk_secret_key="sk_test_development_key").validate_production()


def test_prod_rejects_non_live_clerk_publishable_key() -> None:
    with pytest.raises(RuntimeError, match="CLERK_PUBLISHABLE_KEY"):
        _prod_settings(
            clerk_publishable_key="pk_test_development_key"
        ).validate_production()


def test_prod_missing_clerk_publishable_key_raises() -> None:
    with pytest.raises(RuntimeError, match="CLERK_PUBLISHABLE_KEY"):
        _prod_settings(clerk_publishable_key="").validate_production()


def test_prod_placeholder_clerk_webhook_secret_raises() -> None:
    with pytest.raises(RuntimeError, match="CLERK_WEBHOOK_SECRET"):
        _prod_settings(
            clerk_webhook_secret="whsec_REPLACE_ME"
        ).validate_production()


def test_prod_empty_clerk_jwks_url_raises() -> None:
    with pytest.raises(RuntimeError, match="CLERK_JWKS_URL"):
        _prod_settings(clerk_jwks_url="").validate_production()


def test_prod_empty_clerk_issuer_raises() -> None:
    with pytest.raises(RuntimeError, match="CLERK_ISSUER"):
        _prod_settings(clerk_issuer="").validate_production()


# --- File-token signing key ------------------------------------------------


def test_prod_placeholder_file_token_secret_raises() -> None:
    with pytest.raises(RuntimeError, match="FILE_TOKEN_SECRET"):
        _prod_settings(
            file_token_secret="change-me-min-32-chars-xxxxxxxxxxxx"
        ).validate_production()


def test_prod_short_file_token_secret_raises() -> None:
    with pytest.raises(RuntimeError, match="FILE_TOKEN_SECRET"):
        _prod_settings(file_token_secret="too-short").validate_production()


# --- Testing bypass escape hatches must never land in prod -----------------


def test_prod_testing_bypass_clerk_true_raises() -> None:
    with pytest.raises(RuntimeError, match="TESTING_BYPASS_CLERK"):
        _prod_settings(testing_bypass_clerk=True).validate_production()


def test_prod_testing_clerk_local_secret_set_raises() -> None:
    with pytest.raises(RuntimeError, match="TESTING_CLERK_LOCAL_SECRET"):
        _prod_settings(testing_clerk_local_secret="x" * 32).validate_production()


def test_prod_local_storage_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="STORAGE_PROVIDER"):
        _prod_settings(storage_provider="local").validate_production()


def test_prod_s3_requires_bucket_and_region() -> None:
    with pytest.raises(RuntimeError, match="S3_BUCKET"):
        _prod_settings(s3_bucket="", s3_region="").validate_production()


def test_prod_s3_credentials_must_be_a_pair() -> None:
    with pytest.raises(RuntimeError, match="S3_ACCESS_KEY_ID"):
        _prod_settings(s3_access_key_id="access-key").validate_production()


# --- Payout + payment provider ----------------------------------------------


def test_prod_missing_payout_enc_key_raises() -> None:
    with pytest.raises(RuntimeError, match="PAYOUT_FIELD_ENC_KEY"):
        _prod_settings(payout_field_enc_key="").validate_production()


def test_prod_placeholder_payout_enc_key_raises() -> None:
    with pytest.raises(RuntimeError, match="PAYOUT_FIELD_ENC_KEY"):
        _prod_settings(
            payout_field_enc_key="change-me-base64-32-bytes-xxxxxxxxxxxxxxxxxxxxxxxx"
        ).validate_production()


def test_prod_payout_enc_key_wrong_length_raises() -> None:
    short_key = base64.b64encode(b"\x11" * 16).decode()
    with pytest.raises(RuntimeError, match="PAYOUT_FIELD_ENC_KEY"):
        _prod_settings(payout_field_enc_key=short_key).validate_production()


def test_prod_razorpay_requires_credentials_and_payout_account() -> None:
    with pytest.raises(RuntimeError, match="RAZORPAY_KEY_ID"):
        _prod_settings(payment_provider="razorpay").validate_production()


def test_prod_razorpay_implemented_passes(monkeypatch) -> None:
    class FakeImplementedProvider:
        name = "razorpay"

        def is_implemented(self) -> bool:
            return True

    import app.providers.payment as pay_mod

    monkeypatch.setattr(pay_mod, "get_payment_provider", lambda _s: FakeImplementedProvider())
    _prod_settings(
        payment_provider="razorpay",
        razorpay_key_id="rzp_live_key",
        razorpay_key_secret="live-secret",
        razorpay_webhook_secret="webhook-secret",
        razorpayx_account_number="123456789012",
    ).validate_production()


def test_dev_env_bypasses_all_checks() -> None:
    """A dev-env settings instance with ``*`` CORS and debug on must not raise."""

    s = Settings(
        env="dev",
        debug=True,
        clerk_secret_key="sk_test_REPLACE_ME",
        clerk_publishable_key="pk_test_REPLACE_ME",
        clerk_webhook_secret="whsec_REPLACE_ME",
        clerk_jwks_url="",
        clerk_issuer="",
        file_token_secret="change-me-min-32-chars-xxxxxxxxxxxx",
        testing_bypass_clerk=True,
        testing_clerk_local_secret="x" * 32,
        cors_origins="*",
        enable_mock_payment_endpoints=True,
        payout_field_enc_key="change-me-base64-32-bytes-xxxxxxxxxxxxxxxxxxxxxxxx",
    )  # type: ignore[arg-type]
    s.validate_production()  # must not raise — only enforced in prod
