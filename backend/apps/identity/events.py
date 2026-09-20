"""
Events emitted by the `identity` context.

Event types are versioned public contracts. Payloads stay minimal, avoid
duplicating personal data already owned by identity, and never carry passwords,
device fingerprints, tokens, or other secrets.
"""

from __future__ import annotations

from typing import Any, Final

#: Naming convention describes a completed fact: `<context>.<aggregate>.<past-event>` rather than an
#: imperative command.
USER_REGISTERED: Final = "identity.user.registered"

AGGREGATE_USER: Final = "user"


def user_registered_payload(*, role_name: str) -> dict[str, Any]:
    """Payload for `identity.user.registered` v1; user identity is already carried by aggregate_id."""
    return {"role": role_name}


#: Emis a chaque ouverture de session reussie. Consomme au Sprint 4 par
#: Consumed by notifying for new-login alerts.
USER_LOGGED_IN: Final = "identity.user.logged_in"


def user_logged_in_payload(*, role_name: str, device_bound: bool) -> dict[str, Any]:
    """
    Payload for `identity.user.logged_in` v1; it omits IP, User-Agent, and fingerprint and exposes
    only whether a device was bound.
    """
    return {"role": role_name, "device_bound": device_bound}


#: Emis quand un code de reinitialisation est REELLEMENT cree. Le chemin
#: anti-enumeration — identifiants faux, adresse inconnue — n emet rien : un
#: evenement par tentative transformerait l `outbox` en journal des adresses
#: essayees, ce que la charge utile s interdit par ailleurs.
DEVICE_RESET_REQUESTED: Final = "identity.device.reset.requested"


def device_reset_requested_payload(*, device_bound: bool) -> dict[str, Any]:
    """Payload for device-reset request v1; omit address, code, fingerprint, and challenge identifier."""
    return {"device_bound": device_bound}


#: Emitted after the reset code is verified and the device is unbound.
DEVICE_RESET_CONFIRMED: Final = "identity.device.reset.confirmed"


def device_reset_confirmed_payload(*, device_revoked: bool, sessions_revoked: int) -> dict[str, Any]:
    """Payload for device-reset confirmation v1; include only audit-safe counts, not device identifiers."""
    return {"device_revoked": device_revoked, "sessions_revoked": sessions_revoked}


#: Real password-recovery request.
#: No email address, code, or token is copied into the Outbox.
PASSWORD_RESET_REQUESTED: Final = "identity.password.reset.requested"


def password_reset_requested_payload(
    *,
    challenge_id: Any,
) -> dict[str, Any]:
    return {
        "challenge_id": str(challenge_id),
    }


#: Password successfully reset.
PASSWORD_RESET_COMPLETED: Final = "identity.password.reset.completed"


def password_reset_completed_payload(
    *,
    sessions_revoked: int,
) -> dict[str, Any]:
    return {
        "sessions_revoked": sessions_revoked,
    }


#: Password successfully changed from
#: an authenticated session.
USER_PASSWORD_CHANGED: Final = "identity.user.password_changed"


def user_password_changed_payload(
    *,
    temporary_credential_replaced: bool,
) -> dict[str, Any]:
    """
    No secret is included in the Outbox; the boolean only indicates whether initial scanner
    activation completed.
    """

    return {
        "temporary_credential_replaced": (temporary_credential_replaced),
    }


USER_PROFILE_UPDATED = "identity.user.profile_updated"


def user_profile_updated_payload(
    *,
    changed_fields: list[str],
) -> dict[str, object]:
    return {
        "changed_fields": sorted(set(changed_fields)),
    }


USER_PHONE_CHANGED: Final = "identity.user.phone_changed"


def user_phone_changed_payload(
    *,
    first_record: bool,
) -> dict[str, Any]:
    """
    Indicate only the nature of the change; the phone number remains in identity_user and is not
    duplicated in the Outbox.
    """
    return {
        "first_record": bool(first_record),
    }
