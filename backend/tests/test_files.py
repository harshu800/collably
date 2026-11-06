"""File upload + signed-URL tests.

Covers:
* 413 on each per-type size cap.
* 415 on declared/sniffed MIME mismatch.
* 415 on a wholly unsupported MIME declaration.
* path-traversal filename is safely ignored (storage_key has no user component).
* expired signed URL → 403.
* private file requested with another user's token → 403.
"""

from __future__ import annotations

import io
import os
import struct
import time

import httpx
import pytest

from app.core.security import create_file_token

JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 20
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
PDF_HEADER = b"%PDF-1.4\n" + b"\x00" * 20


def _pad(prefix: bytes, length: int) -> bytes:
    return prefix + b"\x00" * max(0, length - len(prefix))


@pytest.mark.asyncio
async def test_upload_wrong_declared_mime_is_415(
    client: httpx.AsyncClient,
    creator_user: dict,
) -> None:
    headers = creator_user["auth_header"]
    r = await client.post(
        "/api/v1/files",
        files={
            "file": (
                "evil.exe",
                _pad(JPEG_HEADER, 1024),
                "application/x-dosexec",
            )
        },
        headers=headers,
    )
    assert r.status_code == 415, r.text


@pytest.mark.asyncio
async def test_upload_signature_mismatch_is_415(
    client: httpx.AsyncClient,
    creator_user: dict,
) -> None:
    """Declared MIME is in the allowlist but the bytes do not match it."""

    headers = creator_user["auth_header"]
    r = await client.post(
        "/api/v1/files",
        files={
            "file": (
                "fake.png",
                _pad(JPEG_HEADER, 1024),  # JPEG bytes
                "image/png",  # but declared PNG
            )
        },
        headers=headers,
    )
    assert r.status_code == 415, r.text


@pytest.mark.asyncio
async def test_upload_too_large_is_413(
    client: httpx.AsyncClient,
    creator_user: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A body that exceeds the per-type cap is rejected during streaming.

    Tiny per-type cap so we don't have to send 10 MB bytes in a unit test.
    """

    from app.services import storage_service

    monkeypatch.setitem(storage_service.MAX_UPLOAD_BYTES, "image/jpeg", 512)
    headers = creator_user["auth_header"]
    oversized = _pad(JPEG_HEADER, 2048)
    r = await client.post(
        "/api/v1/files",
        files={"file": ("huge.jpg", oversized, "image/jpeg")},
        headers=headers,
    )
    assert r.status_code == 413, r.text


@pytest.mark.asyncio
async def test_upload_happy_path_storage_key_hides_filename(
    client: httpx.AsyncClient,
    creator_user: dict,
    db,
) -> None:
    """A valid JPEG upload lands with a server-generated storage key.

    The key must not contain any user-sourced slug/filename component — a
    path-traversal filename is ignored.
    """

    headers = creator_user["auth_header"]
    body = _pad(JPEG_HEADER, 2048)
    nasty_name = "../../../etc/passwd.jpg"
    r = await client.post(
        "/api/v1/files",
        files={"file": (nasty_name, body, "image/jpeg")},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    file_id = r.json()["id"]

    # Pull the row to inspect its storage_key.
    from app.models.file import File

    row = await db.get(File, file_id)
    assert row is not None
    # Server-generated: <yyyy>/<mm>/<uuid4 hex> — no slashes beyond the two
    # date segments, no 'etc' and no 'passwd'.
    parts = row.storage_key.split("/")
    assert len(parts) == 3
    assert len(parts[0]) == 4 and parts[0].isdigit()
    assert len(parts[1]) == 2 and parts[1].isdigit()
    assert len(parts[2]) == 32 and all(c in "0123456789abcdef" for c in parts[2])
    assert "etc" not in row.storage_key and "passwd" not in row.storage_key


@pytest.mark.asyncio
async def test_signed_url_private_file_wrong_viewer_is_403(
    client: httpx.AsyncClient,
    creator_user: dict,
    brand_user: dict,
) -> None:
    """A token issued to user A should not let user B download the file."""

    headers = creator_user["auth_header"]
    body = _pad(JPEG_HEADER, 2048)
    r = await client.post(
        "/api/v1/files",
        files={"file": ("ok.jpg", body, "image/jpeg")},
        headers=headers,
    )
    assert r.status_code == 201
    file_id = r.json()["id"]

    url_resp = await client.get(f"/api/v1/files/{file_id}/signed-url", headers=headers)
    assert url_resp.status_code == 200
    signed = url_resp.json()["url"]

    # Brand (different user) hits the signed path — token's `sub` points at
    # the creator, so the signed-token guard refuses.
    forbidden = await client.get(signed, headers=brand_user["auth_header"])
    assert forbidden.status_code == 403, forbidden.text


@pytest.mark.asyncio
async def test_signed_url_expired_is_403(
    client: httpx.AsyncClient,
    creator_user: dict,
) -> None:
    """A token minted with an immediate ttl is 403 after it expires."""

    headers = creator_user["auth_header"]
    body = _pad(JPEG_HEADER, 2048)
    r = await client.post(
        "/api/v1/files",
        files={"file": ("ok.jpg", body, "image/jpeg")},
        headers=headers,
    )
    file_id = r.json()["id"]

    # Mint an already-expired token (ttl exceeds the 30s JWT leeway).
    me = await client.get("/api/v1/users/me", headers=headers)
    uid = me.json()["id"]
    expired = create_file_token(file_id=file_id, user_id=uid, ttl_seconds=-120)

    gone = await client.get(f"/api/v1/files/signed/{expired}", headers=headers)
    assert gone.status_code == 403, gone.text


@pytest.mark.asyncio
async def test_signed_url_download_streams_bytes(
    client: httpx.AsyncClient,
    creator_user: dict,
) -> None:
    headers = creator_user["auth_header"]
    body = _pad(JPEG_HEADER, 4096)
    r = await client.post(
        "/api/v1/files",
        files={"file": ("ok.jpg", body, "image/jpeg")},
        headers=headers,
    )
    assert r.status_code == 201
    file_id = r.json()["id"]

    url_resp = await client.get(f"/api/v1/files/{file_id}/signed-url", headers=headers)
    signed = url_resp.json()["url"]

    stream = await client.get(signed, headers=headers)
    assert stream.status_code == 200, stream.text
    assert stream.headers.get("content-type", "").startswith("image/jpeg")
    assert len(stream.content) == len(body)


@pytest.mark.asyncio
async def test_profile_image_is_publicly_viewable(
    client: httpx.AsyncClient,
    creator_user: dict,
) -> None:
    body = _pad(JPEG_HEADER, 2048)
    uploaded = await client.post(
        "/api/v1/files/profile-image",
        files={"file": ("profile.jpg", body, "image/jpeg")},
        headers=creator_user["auth_header"],
    )
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()["id"]

    image = await client.get(f"/api/v1/files/public/{file_id}")
    assert image.status_code == 200, image.text
    assert image.headers.get("content-type", "").startswith("image/jpeg")
    assert image.headers.get("content-disposition") == "inline"
    assert image.content == body


@pytest.mark.asyncio
async def test_public_file_route_does_not_serve_private_uploads(
    client: httpx.AsyncClient,
    creator_user: dict,
) -> None:
    uploaded = await client.post(
        "/api/v1/files",
        files={"file": ("private.jpg", _pad(JPEG_HEADER, 1024), "image/jpeg")},
        headers=creator_user["auth_header"],
    )
    assert uploaded.status_code == 201

    response = await client.get(f"/api/v1/files/public/{uploaded.json()['id']}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_profile_image_upload_only_accepts_images(
    client: httpx.AsyncClient,
    creator_user: dict,
) -> None:
    response = await client.post(
        "/api/v1/files/profile-image",
        files={"file": ("portfolio.pdf", PDF_HEADER, "application/pdf")},
        headers=creator_user["auth_header"],
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_brand_cannot_upload_creator_portfolio_file(
    client: httpx.AsyncClient,
    brand_user: dict,
) -> None:
    response = await client.post(
        "/api/v1/files/creator-portfolio",
        files={"file": ("portfolio.jpg", _pad(JPEG_HEADER, 1024), "image/jpeg")},
        headers=brand_user["auth_header"],
    )
    assert response.status_code == 403


# Silence "unused" warnings on helpers kept for future tests.
_ = (io, os, struct, time, PNG_HEADER, PDF_HEADER)
