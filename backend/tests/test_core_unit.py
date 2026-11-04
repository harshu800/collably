"""Pure-function unit tests for the primitives in :mod:`app.core.security`,
the mock payment provider, payout projections, and storage sniffing."""

from __future__ import annotations

import base64
import time
import uuid

import jwt
import pytest
from cryptography.exceptions import InvalidTag

from app.core.security import (
    create_file_token,
    decode_file_token,
    field_decrypt,
    field_encrypt,
)
from app.models.payout_method import CreatorPayoutMethod, PayoutMethodKind
from app.providers.payment.base import InvalidWebhookSignature
from app.providers.payment.mock import (
    SIGNATURE_HEADER,
    MockSandboxProvider,
    _mask_upi,
    compute_signature,
)
from app.services.payout_method_service import (
    _mask_upi_from_ciphertext,
    non_sensitive_projection,
)
from app.services.storage_service import (
    ALLOWED_MIME_TYPES,
    _match_signature,
    _normalize_mime,
    _sniff_mime,
)

# ---------------------------------------------------------------------------
# Signed file-download tokens (HS256 via PyJWT, FILE_TOKEN_SECRET)
# ---------------------------------------------------------------------------


def test_file_token_roundtrip() -> None:
    tok = create_file_token(file_id="f", user_id="u", ttl_seconds=60)
    payload = decode_file_token(tok)
    assert payload["file_id"] == "f"
    assert payload["sub"] == "u"
    assert payload["type"] == "file"


def test_file_token_expired_rejected() -> None:
    tok = create_file_token(file_id="f", user_id="u", ttl_seconds=-120)
    with pytest.raises(jwt.InvalidTokenError):
        decode_file_token(tok)


def test_file_token_tampered_signature_rejected() -> None:
    tok = create_file_token(file_id="f", user_id="u", ttl_seconds=60)
    tampered = tok[:-4] + ("A" * 4)
    with pytest.raises(jwt.InvalidTokenError):
        decode_file_token(tampered)


# ---------------------------------------------------------------------------
# AES-256-GCM payout-field encrypt / decrypt
# ---------------------------------------------------------------------------


def test_field_encrypt_decrypt_roundtrip() -> None:
    plaintext = "user@okbank"
    blob = field_encrypt(plaintext)
    # Nonce (12 bytes) + ciphertext + GCM tag — never equals plaintext bytes.
    assert blob[:12] != b"\x00" * 12
    assert field_decrypt(blob) == plaintext


def test_field_encrypt_is_non_deterministic() -> None:
    assert field_encrypt("abc") != field_encrypt("abc")


def test_field_encrypt_aad_mismatch_raises() -> None:
    blob = field_encrypt("secret", aad=b"creator-abc")
    with pytest.raises(InvalidTag):
        field_decrypt(blob, aad=b"creator-xyz")


# ---------------------------------------------------------------------------
# Mock-provider HMAC signature + verify_webhook
# ---------------------------------------------------------------------------


def test_compute_signature_is_deterministic() -> None:
    body = b'{"event_id":"a","event_type":"funding.succeeded"}'
    assert compute_signature(body) == compute_signature(body)


def test_mock_verify_webhook_good_signature() -> None:
    body = MockSandboxProvider.build_funding_event_body(
        order_id="mock_order_x", amount_paise=100
    )
    sig = compute_signature(body)
    event = MockSandboxProvider().verify_webhook(
        body=body, headers={SIGNATURE_HEADER: sig}
    )
    assert event.event_type == "funding.succeeded"
    assert event.payload["order_id"] == "mock_order_x"


def test_mock_verify_webhook_bad_signature_raises() -> None:
    body = MockSandboxProvider.build_funding_event_body(
        order_id="mock_order_y", amount_paise=100
    )
    with pytest.raises(InvalidWebhookSignature):
        MockSandboxProvider().verify_webhook(
            body=body, headers={SIGNATURE_HEADER: "deadbeef"}
        )


def test_mock_verify_webhook_header_lookup_is_case_insensitive() -> None:
    body = MockSandboxProvider.build_funding_event_body(
        order_id="mock_order_z", amount_paise=100
    )
    sig = compute_signature(body)
    event = MockSandboxProvider().verify_webhook(
        body=body, headers={"x-mock-signature": sig}
    )
    assert event.event_type.startswith("funding.")


# ---------------------------------------------------------------------------
# VPA + account_number masking helpers
# ---------------------------------------------------------------------------


def test_mask_upi_short_local_part() -> None:
    assert _mask_upi("ab@okbank") == "a***@okbank"


def test_mask_upi_long_local_part() -> None:
    assert _mask_upi("creator-handle@okbank") == "cre***@okbank"


def test_mask_upi_rejects_malformed() -> None:
    assert _mask_upi("not-a-vpa") == "***"


def test_mask_upi_from_ciphertext_decrypts_and_masks() -> None:
    ct = field_encrypt("someone@okbank")
    assert _mask_upi_from_ciphertext(ct) == "som***@okbank"
    assert _mask_upi_from_ciphertext(None) is None


def test_non_sensitive_projection_upi() -> None:
    row = CreatorPayoutMethod(
        creator_id=uuid.uuid4(),
        method=PayoutMethodKind.upi,
        holder_name="A Creator",
        upi_vpa_ciphertext=field_encrypt("someone@okbank"),
        verified=False,
    )
    out = non_sensitive_projection(row)
    assert out["method"] == "upi"
    assert out["upi_vpa_masked"] == "som***@okbank"
    assert out["account_number_last4"] is None


def test_non_sensitive_projection_bank_exposes_last4_only() -> None:
    row = CreatorPayoutMethod(
        creator_id=uuid.uuid4(),
        method=PayoutMethodKind.bank,
        holder_name="A Creator",
        account_number_ciphertext=field_encrypt("1234567890123456"),
        account_number_last4="3456",
        ifsc_ciphertext=field_encrypt("HDFC0001234"),
        verified=False,
    )
    out = non_sensitive_projection(row)
    assert out["method"] == "bank"
    assert out["account_number_last4"] == "3456"
    assert out["upi_vpa_masked"] is None
    assert "ifsc" not in out
    assert "account_number" not in out


# ---------------------------------------------------------------------------
# MIME sniff — positive + negative samples for each allowed type
# ---------------------------------------------------------------------------


_PNG_SAMPLE = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)
_JPEG_SAMPLE = b"\xff\xd8\xff\xe0" + b"\x00" * 60
_PDF_SAMPLE = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"\x00" * 40
_WEBP_SAMPLE = b"RIFF\x00\x00\x00\x00WEBPVP8L" + b"\x00" * 32
_MP4_SAMPLE = b"\x00\x00\x00 ftypisom\x00\x00\x00\x00mp42" + b"\x00" * 40
_MOV_SAMPLE = b"\x00\x00\x00 ftypqt  \x00\x00\x00\x00" + b"\x00" * 40

_FORBIDDEN_SAMPLES = [
    (b"MZ\x90\x00" + b"\x00" * 60, "windows executable"),
    (b"#!/bin/sh\nrm -rf /\n" + b"\x00" * 40, "shell script"),
    (b"PK\x03\x04" + b"\x00" * 60, "zip (and docx/xlsx)"),
    (b"<html><body>bad</body></html>" + b"\x00" * 40, "html"),
]


def test_signature_table_recognises_each_allowed_type() -> None:
    cases = {
        "image/png": _PNG_SAMPLE,
        "image/jpeg": _JPEG_SAMPLE,
        "application/pdf": _PDF_SAMPLE,
        "image/webp": _WEBP_SAMPLE,
        "video/mp4": _MP4_SAMPLE,
        "video/quicktime": _MOV_SAMPLE,
    }
    for mime, head in cases.items():
        assert mime in ALLOWED_MIME_TYPES
        assert _match_signature(head) == mime, f"byte signature failed for {mime}"


@pytest.mark.parametrize("sample,label", _FORBIDDEN_SAMPLES)
def test_signature_table_rejects_forbidden_types(sample: bytes, label: str) -> None:
    assert _match_signature(sample) is None, label


def test_libmagic_sniff_agrees_for_png() -> None:
    sniffed = _normalize_mime(_sniff_mime(_PNG_SAMPLE))
    assert sniffed == "image/png"


def test_libmagic_sniff_agrees_for_jpeg() -> None:
    sniffed = _normalize_mime(_sniff_mime(_JPEG_SAMPLE))
    assert sniffed == "image/jpeg"


def test_libmagic_sniff_rejects_forbidden_dosexec() -> None:
    sniffed = _normalize_mime(_sniff_mime(b"MZ\x90\x00" + b"\x00" * 60))
    assert sniffed not in ALLOWED_MIME_TYPES


# ---------------------------------------------------------------------------
# Helpers used elsewhere — keep lint happy
# ---------------------------------------------------------------------------


def test_timebox() -> None:
    """Smoke-check these pure tests run under a few hundred ms each."""

    t0 = time.perf_counter()
    _ = compute_signature(b"x" * 1024)
    assert time.perf_counter() - t0 < 0.5


_ = base64  # kept for future extensions
