from __future__ import annotations

import mimetypes
import os
import shutil
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

import boto3
from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured

from apps.core.interfaces import ObjectStorage

LOCAL_STORAGE_SIGNING_SALT = "fanid.local-object-storage"


class InMemoryStorage(ObjectStorage):
    """Tests — aucun accès disque ni S3 réel."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def upload(
        self,
        file: BinaryIO,
        key: str,
    ) -> str:
        file.seek(0)
        self._objects[key] = file.read()
        return f"memory://{key}"

    def delete(
        self,
        key: str,
    ) -> None:
        self._objects.pop(key, None)

    def presigned_url(
        self,
        key: str,
        ttl_seconds: int,
    ) -> str:
        if key not in self._objects:
            raise KeyError(f"Objet '{key}' introuvable " "(InMemoryStorage).")

        return f"memory://{key}" f"?ttl={int(ttl_seconds)}"


class LocalStorage(ObjectStorage):
    """
    Stockage objet persistant de développement.

    Les chemins utilisateurs ne sont jamais acceptés directement :
    seule une clé objet contrôlée par le backend est utilisée.
    """

    def __init__(
        self,
        root: str | Path,
    ) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def path_for_key(
        self,
        key: str,
    ) -> Path:
        relative = PurePosixPath(key)

        if not key or relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Clé de stockage invalide.")

        path = self.root.joinpath(*relative.parts).resolve()

        if path != self.root and self.root not in path.parents:
            raise ValueError("Clé de stockage hors racine.")

        return path

    def upload(
        self,
        file: BinaryIO,
        key: str,
    ) -> str:
        destination = self.path_for_key(key)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = destination.with_name((f".{destination.name}." f"{uuid.uuid4().hex}.tmp"))

        file.seek(0)

        try:
            with temporary.open("wb") as target:
                shutil.copyfileobj(
                    file,
                    target,
                )

            os.replace(
                temporary,
                destination,
            )
        finally:
            if temporary.exists():
                temporary.unlink()

        return f"local://{key}"

    def delete(
        self,
        key: str,
    ) -> None:
        path = self.path_for_key(key)

        try:
            path.unlink()
        except FileNotFoundError:
            return

    def presigned_url(
        self,
        key: str,
        ttl_seconds: int,
    ) -> str:
        if ttl_seconds <= 0:
            raise ValueError("Le TTL doit être positif.")

        payload = {
            "key": key,
            "exp": (int(time.time()) + int(ttl_seconds)),
        }

        token = signing.dumps(
            payload,
            salt=LOCAL_STORAGE_SIGNING_SALT,
            compress=True,
        )

        return "/api/v1/storage/local/" f"{token}"


class S3Storage(ObjectStorage):
    """Adaptateur S3 de production."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        client: Any | None = None,
    ) -> None:
        if not bucket:
            raise ImproperlyConfigured("AWS_S3_BUCKET est requis.")

        if not region:
            raise ImproperlyConfigured("AWS_REGION est requis.")

        self.bucket = bucket
        self.region = region
        self.client = (
            client
            if client is not None
            else boto3.client(
                "s3",
                region_name=region,
            )
        )

    def upload(
        self,
        file: BinaryIO,
        key: str,
    ) -> str:
        file.seek(0)

        content_type, _ = mimetypes.guess_type(key)

        extra_args = {}

        if content_type:
            extra_args["ContentType"] = content_type

        kwargs = {}

        if extra_args:
            kwargs["ExtraArgs"] = extra_args

        self.client.upload_fileobj(
            file,
            self.bucket,
            key,
            **kwargs,
        )

        return f"s3://{self.bucket}/{key}"

    def delete(
        self,
        key: str,
    ) -> None:
        self.client.delete_object(
            Bucket=self.bucket,
            Key=key,
        )

    def presigned_url(
        self,
        key: str,
        ttl_seconds: int,
    ) -> str:
        if ttl_seconds <= 0:
            raise ValueError("Le TTL doit être positif.")

        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
            },
            ExpiresIn=int(ttl_seconds),
        )


def resolve_local_presigned_key(
    token: str,
) -> str:
    payload = signing.loads(
        token,
        salt=LOCAL_STORAGE_SIGNING_SALT,
    )

    if not isinstance(payload, dict):
        raise signing.BadSignature("Payload local invalide.")

    key = payload.get("key")
    expires_at = payload.get("exp")

    if not isinstance(key, str) or not key or not isinstance(expires_at, int):
        raise signing.BadSignature("Payload local incomplet.")

    if int(time.time()) >= expires_at:
        raise signing.SignatureExpired("URL locale expirée.")

    return key


def build_object_storage() -> ObjectStorage:
    """
    Sélection fail-closed de l adaptateur.

    - dev/test : disque local persistant ;
    - prod : S3 obligatoire ;
    - OBJECT_STORAGE_BACKEND permet un choix explicite.
    """

    configured = os.environ.get("OBJECT_STORAGE_BACKEND", "").strip().lower()

    environment = (
        str(
            getattr(
                settings,
                "ENVIRONMENT",
                "dev",
            )
        )
        .strip()
        .lower()
    )

    backend = configured or (
        "s3"
        if environment
        in {
            "prod",
            "production",
        }
        else "local"
    )

    if backend == "local":
        configured_root = os.environ.get(
            "OBJECT_STORAGE_LOCAL_ROOT",
            "",
        ).strip()

        root = Path(configured_root) if configured_root else (Path(settings.BASE_DIR) / "mediafiles")

        return LocalStorage(root=root)

    if backend == "s3":
        bucket = os.environ.get("AWS_S3_BUCKET", "").strip()

        region = os.environ.get("AWS_REGION", "").strip()

        return S3Storage(
            bucket=bucket,
            region=region,
        )

    raise ImproperlyConfigured(("OBJECT_STORAGE_BACKEND doit " "valoir 'local' ou 's3'."))
