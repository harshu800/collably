"""LocalFilesystemStorage — the dev-default StorageProvider.

Keys are purely server-generated (``<yyyy>/<mm>/<uuid4-hex>``). After computing
the final absolute path we assert that it still lives under the configured
uploads root as a defensive check against any future refactor accidentally
reintroducing user-sourced path components (design §7.2).
"""

from __future__ import annotations

import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from app.providers.storage.base import StoredObject


class LocalFilesystemStorage:
    name = "local"

    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    # ---- key generation --------------------------------------------------

    def generate_key(self) -> str:
        """Return a fresh ``<yyyy>/<mm>/<uuid4-hex>`` key."""

        now = datetime.now(UTC)
        return f"{now.year:04d}/{now.month:02d}/{uuid.uuid4().hex}"

    # ---- paths -----------------------------------------------------------

    def _resolve(self, key: str) -> Path:
        """Return the absolute path for ``key``, enforcing containment."""

        candidate = (self._root / key).resolve()
        root_prefix = os.path.realpath(str(self._root)) + os.sep
        resolved = os.path.realpath(str(candidate))
        if not (resolved == os.path.realpath(str(self._root)) or resolved.startswith(root_prefix)):
            raise ValueError("Resolved path escapes the uploads root.")
        return candidate

    # ---- StorageProvider -------------------------------------------------

    def put(self, *, key: str, data: BinaryIO, content_type: str) -> StoredObject:
        del content_type  # recorded on the File row, not on disk
        final_path = self._resolve(key)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        with final_path.open("wb") as fh:
            # Stream in chunks so a very large upload never materialises in RAM.
            while True:
                chunk = data.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
                size += len(chunk)
        return StoredObject(key=key, size_bytes=size)

    def open(self, *, key: str) -> BinaryIO:
        return self._resolve(key).open("rb")

    def delete(self, *, key: str) -> None:
        try:
            self._resolve(key).unlink()
        except FileNotFoundError:
            return

    # ---- test helper -----------------------------------------------------

    def _wipe_for_tests(self) -> None:  # pragma: no cover - unused in prod
        shutil.rmtree(self._root, ignore_errors=True)
        self._root.mkdir(parents=True, exist_ok=True)
