"""Application settings and startup production validation.

Settings is a Pydantic-settings model loaded from environment variables (and
``.env`` in dev). ``validate_production()`` fails fast when ``ENV=prod`` is
combined with any insecure default.
"""

from __future__ import annotations

import base64
import ipaddress
from email.utils import parseaddr
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Values that must not appear verbatim in production — placeholder sentinels
# shipped in .env.example. The startup check refuses to boot if they are still
# in use when ENV=prod.
PLACEHOLDER_PAYOUT_ENC_KEY = "change-me-base64-32-bytes-xxxxxxxxxxxxxxxxxxxxxxxx"
PLACEHOLDER_MOCK_WEBHOOK_SECRET = "change-me-mock-secret"
PLACEHOLDER_CLERK_SECRET_KEY = "sk_test_REPLACE_ME"
PLACEHOLDER_CLERK_PUBLISHABLE_KEY = "pk_test_REPLACE_ME"
PLACEHOLDER_CLERK_WEBHOOK_SECRET = "your_clerk_webhook_secret"
PLACEHOLDER_FILE_TOKEN_SECRET = "change-me-min-32-chars-xxxxxxxxxxxx"

FILE_TOKEN_SECRET_MIN_LEN = 32


def _is_https_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


def _is_non_loopback_https_url(value: str) -> bool:
    if not _is_https_url(value):
        return False
    hostname = urlsplit(value).hostname
    if hostname is None or hostname.lower() == "localhost":
        return False
    if hostname.lower().endswith(".localhost"):
        return False
    try:
        return not ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return True


def _is_https_origin(value: str) -> bool:
    if not _is_non_loopback_https_url(value):
        return False
    parsed = urlsplit(value)
    return (
        parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core
    env: Literal["dev", "test", "prod"] = "dev"
    debug: bool = True

    # --- Database (async URL for runtime; sync URL for Alembic)
    database_url: str = (
        "postgresql+asyncpg://marketplace:marketplace@localhost:5432/marketplace"
    )
    database_url_sync: str = (
        "postgresql+psycopg2://marketplace:marketplace@localhost:5432/marketplace"
    )

    # --- Clerk auth
    clerk_secret_key: str = PLACEHOLDER_CLERK_SECRET_KEY
    clerk_publishable_key: str = PLACEHOLDER_CLERK_PUBLISHABLE_KEY
    clerk_webhook_secret: str = PLACEHOLDER_CLERK_WEBHOOK_SECRET
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""

    # --- Signed-file-token signing key (HS256, used by storage_service)
    file_token_secret: str = PLACEHOLDER_FILE_TOKEN_SECRET

    # --- Test-only Clerk bypass
    testing_bypass_clerk: bool = False
    testing_clerk_local_secret: str = ""

    # --- CORS
    cors_origins: str = "http://localhost:3000"
    trust_proxy: bool = False

    # --- Payments
    payment_provider: Literal["mock", "razorpay"] = "mock"
    mock_payment_webhook_secret: str = PLACEHOLDER_MOCK_WEBHOOK_SECRET
    payout_field_enc_key: str = PLACEHOLDER_PAYOUT_ENC_KEY
    enable_mock_payment_endpoints: bool = True

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpayx_account_number: str = ""

  # --- Storage
storage_provider: Literal["local", "s3"] = "local"
storage_local_path: str = "./uploads"
s3_bucket: str = ""
s3_region: str = ""
s3_endpoint_url: str = ""
s3_access_key_id: str = ""
s3_secret_access_key: str = ""

    # --- Email
    email_provider: Literal["console", "smtp"] = "console"
    smtp_host: str = ""
    smtp_port: int | None = None
    smtp_from_email: str = ""
    smtp_username: str = ""
    smtp_password: str = ""

    # --- URLs
    app_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"

    @field_validator("cors_origins")
    @classmethod
    def _strip_cors(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_production(self) -> None:
        """Fail-fast guard for production misconfiguration.

        Raises :class:`RuntimeError` with a human-readable message describing
        every violation found. Called from the FastAPI startup hook when
        ``ENV=prod``.
        """

        if self.env != "prod":
            return

        errors: list[str] = []

        if self.debug:
            errors.append("DEBUG must be false in production")

        # --- Clerk configuration ------------------------------------------------
        if (
            not self.clerk_secret_key
            or self.clerk_secret_key == PLACEHOLDER_CLERK_SECRET_KEY
            or not self.clerk_secret_key.startswith("sk_live_")
        ):
            errors.append(
                "CLERK_SECRET_KEY must be a live Clerk key in production"
            )
        if (
            not self.clerk_publishable_key
            or self.clerk_publishable_key == PLACEHOLDER_CLERK_PUBLISHABLE_KEY
            or not self.clerk_publishable_key.startswith("pk_live_")
        ):
            errors.append(
                "CLERK_PUBLISHABLE_KEY must be a live Clerk key in production"
            )
        if (
            not self.clerk_webhook_secret
            or self.clerk_webhook_secret == PLACEHOLDER_CLERK_WEBHOOK_SECRET
        ):
            errors.append(
                "CLERK_WEBHOOK_SECRET must be set to a real svix secret in production"
            )
        if not _is_non_loopback_https_url(self.clerk_jwks_url):
            errors.append("CLERK_JWKS_URL must be a valid HTTPS URL in production")
        if not _is_non_loopback_https_url(self.clerk_issuer):
            errors.append("CLERK_ISSUER must be a valid HTTPS URL in production")

        # --- File-token signing key --------------------------------------------
        if (
            not self.file_token_secret
            or self.file_token_secret == PLACEHOLDER_FILE_TOKEN_SECRET
            or len(self.file_token_secret) < FILE_TOKEN_SECRET_MIN_LEN
        ):
            errors.append(
                "FILE_TOKEN_SECRET must be set and at least "
                f"{FILE_TOKEN_SECRET_MIN_LEN} characters in production"
            )

        # --- Test-bypass escape hatch must never leak into prod ---------------
        if self.testing_bypass_clerk:
            errors.append("TESTING_BYPASS_CLERK must be false in production")
        if self.testing_clerk_local_secret:
            errors.append(
                "TESTING_CLERK_LOCAL_SECRET must be empty in production"
            )

        # --- CORS + mock endpoint checks (unchanged) --------------------------
        cors_origins = self.cors_origin_list
        if "*" in cors_origins:
            errors.append("CORS_ORIGINS must not contain '*' in production")
        if not cors_origins or any(
            not _is_https_origin(origin) for origin in cors_origins
        ):
            errors.append(
                "CORS_ORIGINS must contain only public HTTPS origins in production"
            )

        if not _is_non_loopback_https_url(self.app_base_url):
            errors.append("APP_BASE_URL must be a valid HTTPS URL in production")
        if not _is_non_loopback_https_url(self.frontend_base_url):
            errors.append(
                "FRONTEND_BASE_URL must be a valid HTTPS URL in production"
            )

        if self.email_provider != "smtp":
            errors.append("EMAIL_PROVIDER must be 'smtp' in production")
        else:
            smtp_host = self.smtp_host.strip()
            if (
                not smtp_host
                or "\r" in smtp_host
                or "\n" in smtp_host
                or "/" in smtp_host
                or ":" in smtp_host
            ):
                errors.append("SMTP_HOST must be set when EMAIL_PROVIDER=smtp")
            if self.smtp_port is None or not 1 <= self.smtp_port <= 65535:
                errors.append("SMTP_PORT must be a valid TCP port")
            sender = self.smtp_from_email.strip()
            sender_address = parseaddr(sender)[1]
            if (
                not sender
                or "\r" in sender
                or "\n" in sender
                or sender_address.count("@") != 1
                or sender_address.startswith("@")
                or sender_address.endswith("@")
            ):
                errors.append(
                    "SMTP_FROM_EMAIL must be a valid sender address"
                )
            if bool(self.smtp_username) != bool(self.smtp_password):
                errors.append(
                    "SMTP_USERNAME and SMTP_PASSWORD must be set together"
                )

        if self.enable_mock_payment_endpoints:
            errors.append(
                "ENABLE_MOCK_PAYMENT_ENDPOINTS must be false in production"
            )

        if (
            not self.payout_field_enc_key
            or self.payout_field_enc_key == PLACEHOLDER_PAYOUT_ENC_KEY
        ):
            errors.append("PAYOUT_FIELD_ENC_KEY must be set in production")
        else:
            # Must be a 32-byte base64 value (AES-256-GCM key).
            try:
                raw = base64.b64decode(self.payout_field_enc_key, validate=True)
                if len(raw) != 32:
                    errors.append(
                        "PAYOUT_FIELD_ENC_KEY must decode to exactly 32 bytes"
                    )
            except Exception:
                errors.append(
                    "PAYOUT_FIELD_ENC_KEY must be valid base64 of a 32-byte key"
                )

        if self.storage_provider != "s3":
            errors.append("STORAGE_PROVIDER must be 's3' in production")
        else:
            if not self.s3_bucket.strip():
                errors.append("S3_BUCKET must be set in production")
            if not self.s3_region.strip():
                errors.append("S3_REGION must be set in production")
            if bool(self.s3_access_key_id) != bool(self.s3_secret_access_key):
                errors.append(
                    "S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY must be set together"
                )

        if self.payment_provider == "razorpay":
            if not self.razorpay_key_id:
                errors.append("RAZORPAY_KEY_ID must be set when Razorpay is enabled")
            if not self.razorpay_key_secret:
                errors.append(
                    "RAZORPAY_KEY_SECRET must be set when Razorpay is enabled"
                )
            if not self.razorpay_webhook_secret:
                errors.append(
                    "RAZORPAY_WEBHOOK_SECRET must be set when Razorpay is enabled"
                )
            if (
                not self.razorpayx_account_number
                or self.razorpayx_account_number
                == "YOUR_RAZORPAYX_ACCOUNT_NUMBER"
            ):
                errors.append(
                    "RAZORPAYX_ACCOUNT_NUMBER must be configured when Razorpay is enabled"
                )
            # Imported lazily to avoid a cycle when provider depends on config.
            from app.providers.payment import get_payment_provider

            provider = get_payment_provider(self)
            if not provider.is_implemented():
                errors.append(
                    "PAYMENT_PROVIDER=razorpay but the configured provider "
                    "is a stub (is_implemented() returned False)"
                )

        if errors:
            joined = "\n  - ".join(errors)
            raise RuntimeError(
                "Production startup check failed:\n  - " + joined
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor so repeated calls do not re-parse env."""

    return Settings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """Test helper — clears the cached Settings so a fresh instance is returned."""

    get_settings.cache_clear()

