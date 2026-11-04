from __future__ import annotations

import io
from typing import Any

import pytest

from app.providers.storage.s3 import S3Storage


class _Body:
    def __init__(self, value: bytes) -> None:
        self._stream = io.BytesIO(value)

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def close(self) -> None:
        self._stream.close()


class _FakeS3Client:
    def __init__(self) -> None:
        self.uploaded: tuple[str, str, bytes, dict[str, Any]] | None = None
        self.deleted: tuple[str, str] | None = None

    def upload_fileobj(
        self, fileobj: io.BytesIO, bucket: str, key: str, *, ExtraArgs: dict[str, Any]
    ) -> None:
        self.uploaded = (bucket, key, fileobj.read(), ExtraArgs)

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, _Body]:
        assert (Bucket, Key) == ("private-bucket", "object/key")
        return {"Body": _Body(b"object-data")}

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.deleted = (Bucket, Key)


def _storage(client: _FakeS3Client) -> S3Storage:
    def client_factory(service: str, **options: str) -> _FakeS3Client:
        assert service == "s3"
        assert options == {"region_name": "ap-south-1"}
        return client

    return S3Storage(
        bucket="private-bucket",
        region="ap-south-1",
        client_factory=client_factory,
    )


def test_upload_uses_private_encrypted_object_and_reports_size() -> None:
    client = _FakeS3Client()
    storage = _storage(client)

    saved = storage.put(
        key="object/key",
        data=io.BytesIO(b"payload"),
        content_type="application/pdf",
    )

    assert saved.key == "object/key"
    assert saved.size_bytes == len(b"payload")
    assert client.uploaded == (
        "private-bucket",
        "object/key",
        b"payload",
        {"ContentType": "application/pdf", "ServerSideEncryption": "AES256"},
    )


def test_open_returns_context_managed_stream_and_closes_body() -> None:
    client = _FakeS3Client()
    storage = _storage(client)

    stream = storage.open(key="object/key")
    with stream as body:
        assert body.read(6) == b"object"
    with pytest.raises(ValueError):
        body.read()


def test_delete_removes_requested_object() -> None:
    client = _FakeS3Client()
    _storage(client).delete(key="object/key")

    assert client.deleted == ("private-bucket", "object/key")


def test_generated_key_does_not_use_user_supplied_data() -> None:
    key = _storage(_FakeS3Client()).generate_key()

    prefix, year, month, object_id = key.split("/")
    assert prefix == "collably"
    assert len(year) == 4 and year.isdigit()
    assert len(month) == 2 and month.isdigit()
    assert len(object_id) == 32


@pytest.mark.parametrize(
    ("bucket", "region", "access_key_id", "secret_access_key", "message"),
    [
        ("", "ap-south-1", "", "", "S3_BUCKET"),
        ("private-bucket", "", "", "", "S3_REGION"),
        ("private-bucket", "ap-south-1", "key", "", "must be configured together"),
    ],
)
def test_invalid_configuration_is_rejected(
    bucket: str,
    region: str,
    access_key_id: str,
    secret_access_key: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        S3Storage(
            bucket=bucket,
            region=region,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
        )
