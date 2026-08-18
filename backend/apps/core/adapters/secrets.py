import os

from apps.core.interfaces import SecretProvider


class EnvSecretProvider(SecretProvider):
    """Dev — lit les secrets depuis les variables d'environnement (`.env`)."""

    def get(self, name: str) -> str:
        value = os.environ.get(name)
        if value is None:
            raise KeyError(f"Secret '{name}' introuvable dans l'environnement.")
        return value

    def get_versioned(self, name: str) -> tuple[str, int]:
        return self.get(name), 1


class FakeSecretProvider(SecretProvider):
    """Tests — dictionnaire en mémoire, aucune dépendance externe."""

    def __init__(self, values: dict[str, str] | None = None):
        self._values = dict(values or {})
        self._versions: dict[str, int] = {k: 1 for k in self._values}

    def set(self, name: str, value: str, version: int = 1) -> None:
        self._values[name] = value
        self._versions[name] = version

    def get(self, name: str) -> str:
        if name not in self._values:
            raise KeyError(f"Secret '{name}' introuvable (FakeSecretProvider).")
        return self._values[name]

    def get_versioned(self, name: str) -> tuple[str, int]:
        return self.get(name), self._versions.get(name, 1)
