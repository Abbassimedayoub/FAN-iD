"""
PolicyEngine — coquille au Sprint 0 (§2.2 Source B, point d'entrée unique
d'autorisation, implémenté au Sprint 1 selon ADR-S-04 Zero Trust : RBAC pour
les capacités, ABAC pour le périmètre).

Le contrat est figé dès maintenant pour que les vues des sprints suivants
appellent systématiquement `PolicyEngine.can(...)` plutôt que des vérifications
de rôle ad hoc dispersées dans les vues.
"""
from typing import Any


class PolicyEngine:
    """Point d'entrée unique de décision d'autorisation (règle 2 ADR-S-04)."""

    @staticmethod
    def can(actor: Any, action: str, resource: Any = None) -> bool:
        raise NotImplementedError(
            "PolicyEngine.can() est une coquille du Sprint 0 — implémentation "
            "RBAC+ABAC livrée au Sprint 1 (identity §5.2)."
        )
