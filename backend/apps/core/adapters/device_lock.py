import time
from typing import Any

from apps.core.interfaces import DeviceLockBackend


class RedisDeviceLock(DeviceLockBackend):
    """
    Implémentation Redis — `SET key value NX EX ttl` : l'atomicité de `SET NX`
    est le mécanisme de verrou (pas de fenêtre de course lecture-puis-écriture).
    Le contenu métier du verrou d'appareil (fingerprint, binding de session)
    est spécifié et implémenté au Sprint 1 ; le Sprint 0 ne fournit que le port
    et cette implémentation générique.
    """

    KEY_PREFIX = "device_lock:"

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    def acquire(self, user_id: str, device_id: str, ttl_seconds: int) -> bool:
        key = f"{self.KEY_PREFIX}{user_id}"
        return bool(self._redis.set(key, device_id, nx=True, ex=ttl_seconds))

    def get_active(self, user_id: str) -> Any | None:
        key = f"{self.KEY_PREFIX}{user_id}"
        value = self._redis.get(key)
        return value.decode() if isinstance(value, bytes) else value

    def release(self, user_id: str) -> None:
        self._redis.delete(f"{self.KEY_PREFIX}{user_id}")


class FakeDeviceLock(DeviceLockBackend):
    """Tests — dictionnaire en mémoire, aucun Redis requis."""

    def __init__(self) -> None:
        self._locks: dict[str, tuple[str, float]] = {}

    def acquire(self, user_id: str, device_id: str, ttl_seconds: int) -> bool:
        existing = self._locks.get(user_id)
        if existing and existing[1] > time.monotonic():
            return False
        self._locks[user_id] = (device_id, time.monotonic() + ttl_seconds)
        return True

    def get_active(self, user_id: str) -> Any | None:
        existing = self._locks.get(user_id)
        if not existing or existing[1] <= time.monotonic():
            return None
        return existing[0]

    def release(self, user_id: str) -> None:
        self._locks.pop(user_id, None)
