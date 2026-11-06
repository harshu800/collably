"""Storage service — upload path with MIME sniff + signed download tokens.

The upload path (``save_upload``) is the single writer for ``File`` rows:

1. Content-Length is validated against the per-type cap (design §9).
2. The first 262 bytes are read for sniffing.
3. ``python-magic`` (libmagic) AND a built-in byte-signature table check must
   both agree with the declared Content-Type and all three must land in the
   allowlist.
4. Only then does the service stream the rest of the body to the
   :class:`StorageProvider` and insert the ``File`` row.

Direct ``uploads/`` serving is explicitly disabled — private file downloads
go through :func:`issue_signed_file_token` + :func:`resolve_signed_file_token`.
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from dataclasses import dataclass
from typing import BinaryIO

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_file_token, decode_file_token
from app.models.file import File, FileVisibility
from app.models.user import User
from app.providers.storage import get_storage_provider

# ---------------------------------------------------------------------------
# python-magic / libmagic — Windows DLL path hint for Python 3.13+.
# ---------------------------------------------------------------------------


# Retained so Python does not drop the DLL-search cookie — if the returned
# object is garbage-collected, the directory leaves the search path.
_MAGIC_DLL_COOKIE: object | None = None


def _add_magic_dll_dir() -> None:
    """On Windows, make the bundled ``python-magic-bin`` DLL loadable.

    Python 3.8+ no longer searches ``PATH`` when ``ctypes.CDLL`` loads a DLL.
    ``python-magic-bin==0.4.14`` ships ``libmagic.dll`` under
    ``site-packages/magic/libmagic/`` but does not call
    :func:`os.add_dll_directory`; so we do it here before importing ``magic``.
    No-op on non-Windows platforms.
    """

    if sys.platform != "win32":  # pragma: no cover - Linux/mac path
        return
    try:  # pragma: no cover - platform-dependent
        import importlib.util

        spec = importlib.util.find_spec("magic")
        if spec is None or spec.origin is None:
            return
        pkg_dir = os.path.dirname(spec.origin)
        libdir = os.path.join(pkg_dir, "libmagic")
        if os.path.isdir(libdir):
            # python-magic's loader uses ``ctypes.util.find_library`` which,
            # on Windows, scans ``PATH`` for the DLL. Prepending the bundled
            # directory to ``PATH`` is what actually makes libmagic loadable
            # on Python 3.13+ — ``os.add_dll_directory`` is not honoured by
            # that loader. Retain the cookie too so secure DLL-search paths
            # keep the directory around for later ``LoadLibraryEx`` calls.
            os.environ["PATH"] = libdir + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                global _MAGIC_DLL_COOKIE
                _MAGIC_DLL_COOKIE = os.add_dll_directory(libdir)
    except Exception:
        # Non-fatal — the subsequent `import magic` will raise if truly broken.
        pass


_add_magic_dll_dir()


def _sniff_mime(head: bytes) -> str:
    """Return the libmagic MIME string for ``head``.

    Imported lazily so the DLL-directory hint above has already run, and so
    the module remains importable in environments where ``libmagic`` is
    unavailable (e.g. test collection on a developer machine without the DLL).
    """

    import magic  # noqa: PLC0415 — intentionally late

    return magic.from_buffer(head, mime=True)


# ---------------------------------------------------------------------------
# Policy tables (design §9)
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "video/mp4",
        "video/quicktime",
        "application/pdf",
    }
)

# Per-type upload cap in bytes.
MAX_UPLOAD_BYTES: dict[str, int] = {
    "image/jpeg": 10 * 1024 * 1024,
    "image/png": 10 * 1024 * 1024,
    "image/webp": 10 * 1024 * 1024,
    "video/mp4": 200 * 1024 * 1024,
    "video/quicktime": 200 * 1024 * 1024,
    "application/pdf": 25 * 1024 * 1024,
}

SNIFF_HEAD_BYTES = 262


# ---------------------------------------------------------------------------
# Byte-signature table (defensive pre-check that must agree with libmagic +
# the declared Content-Type).
# ---------------------------------------------------------------------------


def _match_signature(head: bytes) -> str | None:
    """Return a Content-Type if ``head`` matches a known signature, else ``None``."""

    if len(head) < 4:
        return None
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head[:4] == b"RIFF" and len(head) >= 12 and head[8:12] == b"WEBP":
        return "image/webp"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        major = head[8:12]
        if major == b"qt  ":
            return "video/quicktime"
        # ISO Base Media / MP4 "major_brand" variants.
        if major in {
            b"isom",
            b"mp41",
            b"mp42",
            b"iso2",
            b"iso4",
            b"iso5",
            b"iso6",
            b"avc1",
            b"M4V ",
            b"M4A ",
            b"dash",
        }:
            return "video/mp4"
    return None


def _normalize_mime(value: str | None) -> str:
    """Lowercase + strip any ``; charset=...`` tail so we can compare safely."""

    if not value:
        return ""
    return value.split(";", 1)[0].strip().lower()


# ---------------------------------------------------------------------------
# Upload entry point
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SavedFile:
    file_id: uuid.UUID
    storage_key: str
    size_bytes: int
    content_type: str
    original_filename: str


async def save_upload(
    session: AsyncSession,
    *,
    user: User,
    upload_file: UploadFile,
    content_length: int | None = None,
    visibility: FileVisibility = FileVisibility.private,
    allowed_mime_types: frozenset[str] | None = None,
) -> File:
    """Validate, store, and persist an uploaded file.

    Raises :class:`fastapi.HTTPException` with the status codes documented in
    design §10:

    * 413 — Content-Length exceeds the per-type cap.
    * 415 — Declared or sniffed MIME is not in the allowlist, or they disagree.
    """

    declared = _normalize_mime(upload_file.content_type)
    allowed_types = allowed_mime_types or ALLOWED_MIME_TYPES
    if declared not in allowed_types or declared not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type.",
        )

    max_bytes = MAX_UPLOAD_BYTES[declared]

    # 1) Content-Length-based early-reject (saves reading the body for obvious
    #    oversized uploads).
    if content_length is not None and content_length > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large.",
        )

    # 2) Read the sniff head + the rest, enforcing the byte cap defensively.
    head = await upload_file.read(SNIFF_HEAD_BYTES)

    # 3) Signature table check.
    sig = _match_signature(head)
    if sig is None or sig != declared:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File signature does not match declared type.",
        )

    # 4) libmagic sniff.
    sniffed = _normalize_mime(_sniff_mime(head))
    if sniffed != declared:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Sniffed MIME does not match declared type.",
        )

    # 5) Stream the rest to storage, enforcing the cap byte-by-chunk.
    provider = get_storage_provider()
    storage_key = provider.generate_key()

    total = len(head)
    with tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024, mode="w+b") as buffer:
        buffer.write(head)
        while True:
            chunk = await upload_file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File too large.",
                )
            buffer.write(chunk)
        buffer.seek(0)
        stored = provider.put(key=storage_key, data=buffer, content_type=declared)

    original_filename = (upload_file.filename or "upload")[:512]

    file_row = File(
        owner_user_id=user.id,
        storage_key=stored.key,
        content_type=declared,
        size_bytes=stored.size_bytes,
        original_filename=original_filename,
        visibility=visibility,
    )
    session.add(file_row)
    await session.flush()
    return file_row


# ---------------------------------------------------------------------------
# Signed download tokens
# ---------------------------------------------------------------------------


def issue_signed_file_token(
    *,
    file_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
    ttl_seconds: int = 300,
) -> str:
    return create_file_token(
        file_id=str(file_id),
        user_id=str(user_id),
        ttl_seconds=ttl_seconds,
    )


async def resolve_signed_file_token(
    session: AsyncSession,
    *,
    token: str,
) -> tuple[File, uuid.UUID]:
    """Decode the token and load the referenced ``File``.

    Returns ``(file, token_user_id)``. Raises :class:`fastapi.HTTPException`
    403 on any failure. The caller is responsible for comparing
    ``token_user_id`` to the current viewer when the file is private.
    """

    try:
        payload = decode_file_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired file token.",
        ) from exc

    try:
        file_id = uuid.UUID(payload["file_id"])
        token_user_id = uuid.UUID(payload["sub"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid file token payload.",
        ) from exc

    file_row = await session.get(File, file_id)
    if file_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found.",
        )
    return file_row, token_user_id


def open_file_stream(file_row: File) -> BinaryIO:
    """Open a readable stream for the given file via the active provider."""

    return get_storage_provider().open(key=file_row.storage_key)
