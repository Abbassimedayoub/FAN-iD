from abc import ABC, abstractmethod
from typing import Any


class DeviceLockBackend(ABC):
    """
    Port de verrou d'appareil (§2.3 Source B — clarifie le "verrou d'appareil"
    du dossier d'architecture d'origine, formalisé par le binding de session
    du Sprint 1).

    Implémentations prévues : `RedisDeviceLock` (principal), `PostgresDeviceLock`
    (repli si Redis indisponible), `FakeDeviceLock` (tests — dictionnaire en
    mémoire, aucun Redis requis).
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
