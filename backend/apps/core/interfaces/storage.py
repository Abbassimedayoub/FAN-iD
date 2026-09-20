from abc import ABC, abstractmethod
from typing import BinaryIO


class ObjectStorage(ABC):
    """
    Object-storage port.

    Expected implementations include `S3Storage` for production,
    `LocalStorage` for development, and `InMemoryStorage` for tests without
    real disk or S3 access.
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
