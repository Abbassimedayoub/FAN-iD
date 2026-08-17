"""
Primitives de verrouillage optimiste partagées.

Le compteur de version est porté par VersionedModel. La comparaison et
l'écriture conditionnelle vivent ici afin que les bounded contexts ne
réimplémentent pas chacun leur propre protocole de concurrence.
"""

from typing import Any

from django.db import models

from apps.core.exceptions import PreconditionFailed, StaleResourceError


def parse_if_match(value: str | None) -> int:
    """
    Parse la valeur de l'en-tête If-Match comme une version entière positive.

    L'absence de l'en-tête est une précondition manquante. Une valeur présente
    mais inexploitable est également refusée : elle ne peut pas servir de
    version attendue pour une écriture optimiste.
    """
    if value is None or not value.strip():
        raise PreconditionFailed()

    raw = value.strip()

    # Accepte la représentation HTTP usuelle "3" ainsi que 3.
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        raw = raw[1:-1]

    try:
        version = int(raw)
    except (TypeError, ValueError) as exc:
        raise PreconditionFailed(details={"reason": "If-Match doit contenir une version entière."}) from exc

    if version < 1:
        raise PreconditionFailed(details={"reason": "If-Match doit contenir une version positive."})

    return version


def versioned_update(
    *,
    model: Any,
    pk: Any,
    expected_version: int,
    updates: dict[str, Any],
) -> int:
    """
    Effectue atomiquement UPDATE ... WHERE pk=? AND version=?.

    Retourne la nouvelle version.

    Il ne faut pas remplacer cette primitive par ``instance.save()`` :
    lire la version en Python puis sauvegarder laisse une fenêtre entre la
    comparaison et l'UPDATE, donc deux écrivains concurrents pourraient tous
    deux croire avoir gagné.
    """
    if "version" in updates:
        raise ValueError("version est gérée par versioned_update()")

    updated = model.objects.filter(pk=pk, version=expected_version).update(
        **updates, version=models.F("version") + 1
    )

    if updated == 1:
        return expected_version + 1

    current_version = model.objects.filter(pk=pk).values_list("version", flat=True).first()

    raise StaleResourceError(details={"current_version": current_version})


def format_etag(version: int) -> str:
    """Retourne la représentation HTTP d'une version pour l'en-tête ETag."""
    return f'"{version}"'
