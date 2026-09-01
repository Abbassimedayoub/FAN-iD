from __future__ import annotations

import io

import pytest
from django.core import signing

from apps.core.adapters.storage import LocalStorage, S3Storage, resolve_local_presigned_key

PNG = b"\x89PNG\r\n\x1a\n" + b"fanid-image"


def test_local_storage_round_trip_and_signed_url(
    tmp_path,
):
    storage = LocalStorage(tmp_path)

    key = "events/org/event/poster.png"

    result = storage.upload(
        io.BytesIO(PNG),
        key,
    )

    assert result == f"local://{key}"
    assert storage.path_for_key(key).read_bytes() == PNG

    url = storage.presigned_url(
        key,
        300,
    )

    token = url.rsplit("/", 1)[-1]

    assert resolve_local_presigned_key(token) == key

    storage.delete(key)

    assert not storage.path_for_key(key).exists()


def test_local_storage_rejects_path_traversal(
    tmp_path,
):
    storage = LocalStorage(tmp_path)

    with pytest.raises(ValueError):
        storage.upload(
            io.BytesIO(PNG),
            "../outside.png",
        )


def test_local_signed_url_rejects_tampering(
    tmp_path,
):
    storage = LocalStorage(tmp_path)

    url = storage.presigned_url(
        "events/a.png",
        300,
    )

    token = url.rsplit("/", 1)[-1]

    with pytest.raises(signing.BadSignature):
        resolve_local_presigned_key(token + "tampered")


class FakeS3Client:
    def __init__(self):
        self.uploads = []
        self.deletes = []

    def upload_fileobj(
        self,
        file,
        bucket,
        key,
        **kwargs,
    ):
        self.uploads.append(
            (
                file.read(),
                bucket,
                key,
                kwargs,
            )
        )

    def delete_object(
        self,
        *,
        Bucket,
        Key,
    ):
        self.deletes.append(
            (
                Bucket,
                Key,
            )
        )

    def generate_presigned_url(
        self,
        operation,
        *,
        Params,
        ExpiresIn,
    ):
        return "https://signed.example.test/" f"{Params['Key']}" f"?ttl={ExpiresIn}"


def test_s3_storage_uses_private_object_key():
    client = FakeS3Client()

    storage = S3Storage(
        bucket="fanid-private",
        region="eu-west-3",
        client=client,
    )

    key = "events/org/event/poster.png"

    uploaded = storage.upload(
        io.BytesIO(PNG),
        key,
    )

    assert uploaded == ("s3://fanid-private/" f"{key}")

    assert client.uploads[0][1] == ("fanid-private")
    assert client.uploads[0][2] == key

    url = storage.presigned_url(
        key,
        300,
    )

    assert url.startswith("https://signed.example.test/")

    storage.delete(key)

    assert client.deletes == [
        (
            "fanid-private",
            key,
        )
    ]
