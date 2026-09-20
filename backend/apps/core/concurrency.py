"""
Shared optimistic-locking primitives.

VersionedModel owns the version counter while comparison and conditional writes
live here so bounded contexts do not each reimplement the concurrency protocol.
"""

from typing import Any

from django.db import models

from apps.core.exceptions import PreconditionFailed, StaleResourceError


def parse_if_match(value: str | None) -> int:
    """Parse If-Match as a positive integer version and reject missing or unusable preconditions."""
    if value is None or not value.strip():
        raise PreconditionFailed()

    raw = value.strip()

    # Accept the usual HTTP representation "3" as well as 3.
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
    Atomically perform UPDATE ... WHERE pk=? AND version=? and return the new version.

    Do not replace this with a read followed by `instance.save()`; that would
    reopen a race window between comparison and update.
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
    """Return the HTTP representation of a version for the ETag header."""
    return f'"{version}"'
