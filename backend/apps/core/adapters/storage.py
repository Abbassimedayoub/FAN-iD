from typing import BinaryIO

from apps.core.interfaces import ObjectStorage


class InMemoryStorage(ObjectStorage):
    """Tests — aucun accès disque ni S3 réel."""

    def __init__(self):
        self._objects: dict[str, bytes] = {}

    def upload(self, file: BinaryIO, key: str) -> str:
        self._objects[key] = file.read()
        return f"memory://{key}"

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    def presigned_url(self, key: str, ttl_seconds: int) -> str:
        if key not in self._objects:
            raise KeyError(f"Objet '{key}' introuvable (InMemoryStorage).")
        return f"memory://{key}?ttl={ttl_seconds}"
