"""StorageProvider protocol + the ``StoredObject`` return type.

Implementations: :class:`app.providers.storage.local.LocalFilesystemStorage`
and :class:`app.providers.storage.s3.S3Storage`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Protocol, runtime_checkable


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int


@runtime_checkable
class StorageProvider(Protocol):
    """Minimum contract the service layer depends on."""

    name: str

    def generate_key(self) -> str: ...

    def put(self, *, key: str, data: BinaryIO, content_type: str) -> StoredObject: ...

    def open(self, *, key: str) -> BinaryIO: ...

    def delete(self, *, key: str) -> None: ...
