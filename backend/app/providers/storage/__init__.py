"""Storage provider factory. Reads ``STORAGE_PROVIDER`` from settings."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.storage.base import StorageProvider, StoredObject
from app.providers.storage.local import LocalFilesystemStorage


def _build_provider(settings: Settings) -> StorageProvider:
    name = settings.storage_provider
    if name == "local":
        return LocalFilesystemStorage(root_path=settings.storage_local_path)
    if name == "s3":
        from app.providers.storage.s3 import S3Storage

        return S3Storage(
    bucket=settings.s3_bucket,
    region=settings.s3_region,
    endpoint_url=settings.s3_endpoint_url,
    access_key_id=settings.s3_access_key_id,
    secret_access_key=settings.s3_secret_access_key,
)
    raise RuntimeError(f"Unknown STORAGE_PROVIDER: {name!r}")


@lru_cache(maxsize=1)
def get_storage_provider() -> StorageProvider:
    """Cached accessor so FastAPI dependencies share a single provider."""

    return _build_provider(get_settings())


def reset_storage_provider_cache() -> None:
    """Test helper — forces the next ``get_storage_provider`` call to rebuild."""

    get_storage_provider.cache_clear()


__all__ = [
    "StorageProvider",
    "StoredObject",
    "get_storage_provider",
    "reset_storage_provider_cache",
]
