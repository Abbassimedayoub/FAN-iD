from abc import ABC, abstractmethod


class SecretProvider(ABC):
    """
    Port d'accès aux secrets (§2.3 Source B).

    Implémentations prévues : `SsmSecretProvider` (prod, AWS SSM+KMS),
    `EnvSecretProvider` (dev, variables d'environnement), `FakeSecretProvider`
    (tests, valeurs en mémoire — jamais un vrai secret AWS n'est requis pour
    faire tourner la suite de tests).
    """

    @abstractmethod
    def get(self, name: str) -> str:
        """Retourne la valeur courante du secret `name`. Lève KeyError si absent."""
        raise NotImplementedError

    @abstractmethod
    def get_versioned(self, name: str) -> tuple[str, int]:
        """Retourne (valeur, version) — nécessaire à la rotation de clé (ex. QR_SEED)."""
        raise NotImplementedError
