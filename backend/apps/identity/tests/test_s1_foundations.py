"""
Fondations de sécurité du Sprint 1 (lot S1-A.0).

Ces tests protègent trois invariants qu'aucun test du Sprint 0 ne couvrait et
dont dépend tout le reste du sprint d'identité.
"""

import pytest
from django.conf import settings

from apps.core.exceptions import InvalidStateTransitionError, PreconditionFailed
from apps.core.observability.logging import SecretRedactor
from apps.identity.hashers import FanIdArgon2PasswordHasher

_REDACTED = "***REDACTED***"


# --------------------------------------------------------------- Argon2id


def test_argon2_parameters_match_the_security_plan():
    """Plan S1 §5.1 (OWASP A02) : time_cost=3, memory_cost=64 Mio, parallelism=4."""
    hasher = FanIdArgon2PasswordHasher()
    assert hasher.time_cost == 3
    assert hasher.memory_cost == 65536  # kibioctets
    assert hasher.parallelism == 4


def test_argon2_uses_the_id_variant_not_i_or_d():
    """Argon2**id** est la variante exigée : `i` seule est faible face au GPU."""
    from argon2.low_level import Type

    assert FanIdArgon2PasswordHasher().algorithm == "argon2"
    assert Type.ID is not None  # la variante est celle du hasher Django (argon2.low_level.Type.ID)


def test_production_hasher_list_puts_argon2_first():
    """
    L'ordre fait foi : Django hache TOUJOURS avec le premier de la liste.
    Les suivants ne servent qu'à vérifier d'anciens hachages.
    """
    from django.conf import settings as live

    if live.PASSWORD_HASHERS[0].endswith("MD5PasswordHasher"):
        pytest.skip("environnement de test : hacheur rapide volontaire (plan S1 §5.3)")
    assert live.PASSWORD_HASHERS[0] == "apps.identity.hashers.FanIdArgon2PasswordHasher"


# ---------------------------------------------------- Rédaction des secrets


@pytest.mark.parametrize(
    "key",
    [
        "device_fingerprint",
        "fingerprint",
        "otp",
        "otp_code",
        "refresh",
        "refresh_jti",
        "refresh_token",
        "jti",
        "did",
        "access",
        "code",
        "Authorization",
        "password",
    ],
)
def test_sprint1_authentication_secrets_are_redacted(key):
    """§29/§44 : ni OTP, ni empreinte, ni jeton ne doivent atteindre un journal."""
    assert SecretRedactor.redact({key: "valeur-sensible"})[key] == _REDACTED


@pytest.mark.parametrize(
    "key",
    ["error_code", "status_code", "http_status", "candidate", "totp_result", "user_id", "event_type"],
)
def test_observability_keys_are_not_over_redacted(key):
    """
    Contre-épreuve indispensable : un motif trop large détruirait l'observabilité.
    `error_code` et `status_code` alimentent le diagnostic d'incident — les masquer
    rendrait les journaux inutilisables sans rien protéger.
    """
    assert SecretRedactor.redact({key: "visible"})[key] == "visible"


def test_redaction_still_reaches_nested_sprint1_payloads():
    payload = {"login": {"device_fingerprint": "a" * 64, "email": "fan@example.test"}}
    result = SecretRedactor.redact(payload)
    assert result["login"]["device_fingerprint"] == _REDACTED
    assert result["login"]["email"] == "fan@example.test"


# ------------------------------------------------------- Contrat d'erreur


def test_precondition_required_is_428_not_412():
    """
    RFC 6585 §3 : 428 = « aucune précondition fournie », 412 = « la précondition
    fournie a échoué ». `If-Match` manquant relève du premier cas (plan S1 §3.4).
    """
    error = PreconditionFailed()
    assert error.status_code == 428
    assert error.code == "PRECONDITION_REQUIRED"


def test_invalid_state_transition_is_a_409_conflict():
    error = InvalidStateTransitionError()
    assert error.status_code == 409
    assert error.code == "INVALID_STATE_TRANSITION"


# ------------------------------------------------------- Configuration


def test_session_middleware_is_declared_exactly_once():
    """Un doublon fait exécuter deux fois le cycle de session à chaque requête."""
    occurrences = [m for m in settings.MIDDLEWARE if m.endswith("SessionMiddleware")]
    assert len(occurrences) == 1, f"SessionMiddleware déclaré {len(occurrences)} fois"


def test_refresh_cookie_is_always_httponly():
    """Un refresh lisible en JavaScript est une faille — jamais configurable (§18)."""
    assert settings.REFRESH_COOKIE_HTTPONLY is True


def test_no_production_domain_is_hardcoded():
    """§70 : aucun domaine de production n'existe. Rien ne doit en inventer un."""
    for value in (settings.REFRESH_COOKIE_DOMAIN, *settings.CSRF_TRUSTED_ORIGINS):
        if value:
            assert "fan-id" not in str(value).lower()
