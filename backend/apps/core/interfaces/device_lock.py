from abc import ABC, abstractmethod
from typing import Any


class DeviceLockBackend(ABC):
    """
    Device-lock port used by session/device binding.

    Expected implementations include `RedisDeviceLock` as the primary backend,
    `PostgresDeviceLock` as a fallback when Redis is unavailable, and
    `FakeDeviceLock` for tests without Redis.
    """

    @abstractmethod
    def acquire(self, user_id: str, device_id: str, ttl_seconds: int) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_active(self, user_id: str) -> Any | None:
        raise NotImplementedError

    @abstractmethod
    def release(self, user_id: str) -> None:
        raise NotImplementedError
