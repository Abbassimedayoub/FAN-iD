from abc import ABC, abstractmethod
from typing import BinaryIO


class ObjectStorage(ABC):
    """
    Port de stockage objet (§2.3 Source B).

    Implémentations prévues : `S3Storage` (prod), `LocalStorage` (dev, disque
    local), `InMemoryStorage` (tests — aucun accès disque ni S3 réel).
    """

    @abstractmethod
    def upload(self, file: BinaryIO, key: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def presigned_url(self, key: str, ttl_seconds: int) -> str:
        raise NotImplementedError
