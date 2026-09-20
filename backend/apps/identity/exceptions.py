"""
Business errors for the `identity` context.

They inherit from the shared `core` hierarchy instead of defining a second
error contract. The system therefore keeps one shape for `code`, `message`,
`details`, `correlation_id`, and `trace_id`.

The dependency direction remains one-way: `identity` may depend on `core`,
while `core` must not know about identity-specific errors.
"""

from __future__ import annotations

from apps.core.exceptions import AuthError, PermissionBusinessError, RateLimitError, ValidationBusinessError


class EmailAlreadyExistsError(ValidationBusinessError):
    """
    400 — the address is already used.

    The 400 status is part of the published API contract even though 409 could
    also describe a resource conflict. Once clients depend on an error contract,
    compatibility matters more than changing the semantic choice later.

    Account existence disclosure is an explicit tradeoff here. A fully opaque
    registration flow would require a notification channel capable of resolving
    duplicate registrations out-of-band. Until that exists, throttling makes
    enumeration more expensive while keeping the registration experience usable.
    """

    default_code = "EMAIL_ALREADY_EXISTS"
    default_message = "Un compte existe deja pour cette adresse."


class UnderageError(ValidationBusinessError):
    """
    400 — minimum age is not met.

    The database already enforces `ck_user_min_age_16`, but a database
    IntegrityError would produce an unusable client response. The service checks
    first for a readable error while the database constraint remains the final
    integrity guard for direct writes.
    """

    default_code = "UNDERAGE"
    default_message = "L inscription est reservee aux personnes de 16 ans et plus."


class TermsNotAcceptedError(ValidationBusinessError):
    """400 — required terms have not been accepted."""

    default_code = "TERMS_NOT_ACCEPTED"
    default_message = "L acceptation des conditions generales est obligatoire."


class InvalidFingerprintError(ValidationBusinessError):
    """
    400 — malformed device fingerprint or unknown platform.

    The fingerprint is computed client-side and remains opaque to the server.
    The server validates only the canonical format and rejects malformed input
    instead of silently normalizing it.
    """

    default_code = "INVALID_FINGERPRINT"
    default_message = "L empreinte d appareil est invalide."


class DeviceLockedError(PermissionBusinessError):
    """
    403 — another device is already bound to the account.

    `details` contains only enough information for the account owner to
    recognize the active device without disclosing unnecessary information.

    This error must never be returned before credential verification. Invalid
    credentials on a locked account still return `INVALID_CREDENTIALS`, so the
    API does not confirm account existence to an unauthenticated caller.
    """

    default_code = "DEVICE_LOCKED"
    default_message = "Un autre appareil est deja associe a ce compte."


class DeviceMismatchError(AuthError):
    """
    401 — token presented from a device other than the bound device.

    This is intentionally authentication failure rather than authorization
    failure: a valid token presented from another device may be stolen, so the
    caller's identity is not considered proven.
    """

    default_code = "DEVICE_MISMATCH"
    default_message = "Ce jeton ne provient pas de l appareil associe au compte."


class InvalidCredentialsError(AuthError):
    """
    401 — unknown address, wrong password, or disabled account.

    One public code deliberately covers all three cases. Distinguishing them
    would turn authentication into an account-existence oracle. Response timing
    must also remain comparable; see the authentication service's dummy hash.
    """

    default_code = "INVALID_CREDENTIALS"
    default_message = "Adresse ou mot de passe incorrect."


class InvalidCurrentPasswordError(ValidationBusinessError):
    """
    400 `VALIDATION_ERROR` — the current password does not match.

    The caller is already authenticated, so this is a body-field validation
    error rather than a 401 authentication failure. Returning 401 would cause
    clients to treat a typo as session expiry.
    """

    default_code = "VALIDATION_ERROR"
    default_message = "Le mot de passe actuel est incorrect."


class PasswordUnchangedError(ValidationBusinessError):
    """
    400 `VALIDATION_ERROR` — the new password matches the old password.

    Rejecting this avoids revoking every session for a change that produced no
    actual credential update.
    """

    default_code = "VALIDATION_ERROR"
    default_message = "Le nouveau mot de passe doit etre different de l ancien."


class OtpInvalidError(ValidationBusinessError):
    """
    400 `OTP_INVALID` — challenge missing, expired, consumed, or code invalid.

    One public code intentionally covers all these states so an attacker cannot
    infer whether a challenge ever existed for a guessed account.
    """

    default_code = "OTP_INVALID"
    default_message = "Code invalide ou expire."


class OtpMaxAttemptsError(RateLimitError):
    """
    429 `OTP_MAX_ATTEMPTS` — the five-attempt limit has been reached.

    Once this happens the challenge is permanently consumed; even the correct
    code cannot reopen it and the user must request a new challenge.
    """

    default_code = "OTP_MAX_ATTEMPTS"
    default_message = "Trop de tentatives. Demandez un nouveau code."
