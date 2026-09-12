from __future__ import annotations

import io

import pytest
from django.core import signing
from django.core.exceptions import ImproperlyConfigured

from apps.core.adapters import storage as storage_module
from apps.core.adapters.storage import (
    LocalStorage,
    R2Storage,
    build_object_storage,
    resolve_local_presigned_key,
)

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


class FakeR2Client:
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
        return "https://signed.example.test/" f"{Params['Key']}?ttl={ExpiresIn}"


def test_r2_storage_uses_private_object_key():
    client = FakeR2Client()

    storage = R2Storage(
        bucket="fanid-private",
        account_id="0123456789abcdef0123456789abcdef",
        access_key_id="test-access-key",
        secret_access_key="test-secret-key",
        client=client,
    )

    key = "events/org/event/poster.png"

    uploaded = storage.upload(
        io.BytesIO(PNG),
        key,
    )

    assert uploaded == f"r2://fanid-private/{key}"
    assert client.uploads[0][1] == "fanid-private"
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


def test_build_object_storage_configures_r2(
    settings,
    monkeypatch,
):
    captured = {}
    fake_client = FakeR2Client()

    def fake_boto3_client(
        service_name,
        **kwargs,
    ):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return fake_client

    monkeypatch.setattr(
        storage_module.boto3,
        "client",
        fake_boto3_client,
    )

    settings.OBJECT_STORAGE_BACKEND = "r2"
    settings.R2_ACCOUNT_ID = "0123456789abcdef0123456789abcdef"
    settings.R2_ACCESS_KEY_ID = "test-access-key"
    settings.R2_SECRET_ACCESS_KEY = "test-secret-key"
    settings.R2_BUCKET = "fanid-private"

    storage = build_object_storage()

    assert isinstance(storage, R2Storage)
    assert captured["service_name"] == "s3"
    assert captured["region_name"] == "auto"
    assert captured["endpoint_url"] == (
        "https://0123456789abcdef0123456789abcdef" ".r2.cloudflarestorage.com"
    )
    assert captured["aws_access_key_id"] == ("test-access-key")
    assert captured["aws_secret_access_key"] == ("test-secret-key")


def test_build_object_storage_rejects_legacy_s3_backend(
    settings,
):
    settings.OBJECT_STORAGE_BACKEND = "s3"

    with pytest.raises(ImproperlyConfigured):
        build_object_storage()


def test_r2_storage_rejects_invalid_account_id():
    with pytest.raises(ImproperlyConfigured):
        R2Storage(
            bucket="fanid-private",
            account_id="invalid-account-id",
            access_key_id="test-access-key",
            secret_access_key="test-secret-key",
        )
