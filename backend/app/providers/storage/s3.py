

"""Private S3-compatible object storage."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, BinaryIO, cast

import boto3

from app.providers.storage.base import StoredObject


class S3Storage:
    name = "s3"
    _key_prefix = "collably"

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str = "",
        access_key_id: str = "",
        secret_access_key: str = "",
        client_factory: Callable[..., Any] = boto3.client,
    ) -> None:
        if not bucket.strip():
            raise ValueError("S3_BUCKET must be configured.")

        if not region.strip():
            raise ValueError("S3_REGION must be configured.")

        if bool(access_key_id) != bool(secret_access_key):
            raise ValueError(
                "S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY "
                "must be configured together."
            )

        self._bucket = bucket

        client_options: dict[str, str] = {
            "region_name": region,
        }

        if endpoint_url.strip():
            client_options["endpoint_url"] = endpoint_url.strip()

        if access_key_id:
            client_options["aws_access_key_id"] = access_key_id
            client_options["aws_secret_access_key"] = secret_access_key

        self._client = client_factory("s3", **client_options)

    def generate_key(self) -> str:
        """Return a server-generated, non-user-identifying object key."""

        now = datetime.now(UTC)

        return (
            f"{self._key_prefix}/{now.year:04d}/{now.month:02d}/"
            f"{uuid.uuid4().hex}"
        )

    def put(
        self,
        *,
        key: str,
        data: BinaryIO,
        content_type: str,
    ) -> StoredObject:
        start = data.tell()
        data.seek(0, 2)
        size = data.tell() - start
        data.seek(start)

        self._client.upload_fileobj(
            data,
            self._bucket,
            key,
            ExtraArgs={
                "ContentType": content_type,
            },
        )

        return StoredObject(key=key, size_bytes=size)

    def open(self, *, key: str) -> BinaryIO:
        response = self._client.get_object(
            Bucket=self._bucket,
            Key=key,
        )

        return cast(BinaryIO, _S3BodyStream(response["Body"]))

    def delete(self, *, key: str) -> None:
        self._client.delete_object(
            Bucket=self._bucket,
            Key=key,
        )


class _S3BodyStream:
    """Provide context-manager cleanup for boto3's non-context-managed body."""

    def __init__(self, body: object) -> None:
        self._body = body

    def __enter__(self) -> _S3BodyStream:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def read(self, size: int = -1) -> bytes:
        return cast(BinaryIO, self._body).read(size)

    def close(self) -> None:
        cast(BinaryIO, self._body).close()
