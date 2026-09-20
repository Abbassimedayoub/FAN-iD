from abc import ABC, abstractmethod


class SecretProvider(ABC):
    """
    Secret-access port.

    Expected implementations include `SsmSecretProvider` for production,
    `EnvSecretProvider` for development, and `FakeSecretProvider` for tests
    with in-memory values.
    """

    @abstractmethod
    def get(self, name: str) -> str:
        """Return the current value for `name`; raise KeyError when absent."""
        raise NotImplementedError

    @abstractmethod
    def get_versioned(self, name: str) -> tuple[str, int]:
        """Return `(value, version)`, required for key-rotation workflows."""
        raise NotImplementedError
