"""
Contrat des cinq familles de métriques métier du Sprint 1.

Les incréments métier sont testés séparément côté identity.
Ici on vérifie les noms, types, labels et la cardinalité.
"""

from __future__ import annotations

import pytest

from apps.core.observability import metrics

EXPECTED: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("fanid_auth_login_total", "fanid_auth_login", ("result",)),
    ("fanid_auth_token_refresh_total", "fanid_auth_token_refresh", ("result",)),
    ("fanid_auth_token_reuse_detected_total", "fanid_auth_token_reuse_detected", ()),
    ("fanid_device_reset_total", "fanid_device_reset", ("result",)),
    ("fanid_authz_denied_total", "fanid_authz_denied", ("action", "role")),
)

FORBIDDEN_LABEL_FRAGMENTS = (
    "user",
    "email",
    "ip",
    "address",
    "session",
    "device",
    "token",
    "organizer",
    "challenge",
    "fingerprint",
    "uuid",
)


def _labelnames(metric: object) -> tuple[str, ...]:
    return tuple(getattr(metric, "_labelnames", ()))


@pytest.mark.parametrize(("attribute", "internal_name", "labels"), EXPECTED)
def test_each_business_metric_is_declared_with_its_exact_contract(
    attribute: str,
    internal_name: str,
    labels: tuple[str, ...],
) -> None:
    metric = getattr(metrics, attribute, None)

    assert metric is not None, f"{attribute} n'est pas déclarée"
    assert metric._name == internal_name
    assert metric._type == "counter"
    assert _labelnames(metric) == labels
    assert metric._documentation


@pytest.mark.parametrize("attribute", [row[0] for row in EXPECTED])
def test_no_business_metric_carries_an_unbounded_label(attribute: str) -> None:
    for label in _labelnames(getattr(metrics, attribute)):
        for fragment in FORBIDDEN_LABEL_FRAGMENTS:
            assert fragment not in label.lower(), (
                f"{attribute} porte le label {label!r}, " f"qui contient {fragment!r}"
            )


@pytest.mark.parametrize("attribute", [row[0] for row in EXPECTED])
def test_naming_convention_is_respected(attribute: str) -> None:
    assert attribute.startswith("fanid_")
    assert attribute.endswith("_total")


def test_the_reuse_counter_has_no_label_at_all() -> None:
    assert _labelnames(metrics.fanid_auth_token_reuse_detected_total) == ()


def test_the_anonymous_role_label_is_a_closed_literal() -> None:
    assert metrics.AUTHZ_ROLE_ANONYMOUS == "anonymous"
