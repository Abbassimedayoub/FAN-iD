"""
Role reference data.

Identifiers are **fixed and derived deterministically** with UUIDv5 rather than
generated dynamically. This provides three benefits:

1. A migration adding `user.role_id` as NOT NULL can use a known value while
   the migration is authored.
2. Identifiers stay identical across development, tests, CI, and production,
   so fixtures and demo datasets remain portable.
3. Seeding is genuinely idempotent: replaying it cannot create a duplicate
   role under a new identifier.

`Role.permissions` (jsonb) is descriptive and shown in administration tools.
It is NEVER the source of truth for authorization; the code policy engine is.
"""

import uuid

ROLE_FAN = "FAN"
ROLE_ORGANIZER = "ORGANIZER"
ROLE_SCANNER = "SCANNER"
ROLE_ADMIN = "ADMIN"

#: Stable ordering used by the CHECK constraint and policy-matrix tests.
ROLE_NAMES: tuple[str, ...] = (ROLE_FAN, ROLE_ORGANIZER, ROLE_SCANNER, ROLE_ADMIN)

#: Role assigned to every public registration; public signup cannot assign
#: arbitrary privileges.
DEFAULT_ROLE = ROLE_FAN

ROLE_IDS: dict[str, uuid.UUID] = {
    ROLE_FAN: uuid.UUID("80d63969-f419-5bd6-b682-653e21e74a65"),
    ROLE_ORGANIZER: uuid.UUID("ea173779-0ab3-56b8-9924-23915ef7fc29"),
    ROLE_SCANNER: uuid.UUID("91e56bcb-d23e-5169-a1f3-655e1e44f277"),
    ROLE_ADMIN: uuid.UUID("58d71579-cab7-576e-b233-27c1c424b8bd"),
}


# ---------------------------------------------------------------- devices

#: Device fingerprint format.
#: The fingerprint is computed CLIENT-SIDE and remains opaque to the server. The
#: server never recomputes it or infers anything from it; it only validates the
#: format: 64 LOWERCASE hexadecimal characters, i.e. canonical SHA-256.
#: Accepting uppercase would create two representations of the same fingerprint
#: and therefore two logical devices for one physical phone.
FINGERPRINT_PATTERN = r"^[0-9a-f]{64}$"

PLATFORM_ANDROID = "android"
PLATFORM_IOS = "ios"
PLATFORM_WEB = "web"
DEVICE_PLATFORMS: tuple[str, ...] = (PLATFORM_ANDROID, PLATFORM_IOS, PLATFORM_WEB)

DEVICE_REVOKED_USER_RESET = "USER_RESET"
DEVICE_REVOKED_ADMIN = "ADMIN"
DEVICE_REVOKED_PASSWORD_CHANGE = "PASSWORD_CHANGE"
DEVICE_REVOKED_STALE = "STALE"
DEVICE_REVOKED_REASONS: tuple[str, ...] = (
    DEVICE_REVOKED_USER_RESET,
    DEVICE_REVOKED_ADMIN,
    DEVICE_REVOKED_PASSWORD_CHANGE,
    DEVICE_REVOKED_STALE,
)

# ----------------------------------------------------------------- sessions

#: Authentication level carried by the session and JWT.
#: 1 = password only. 2 = step-up verification, such as a code received by email.
#: Sensitive actions such as device reset, email change, and account deletion
#: require level 2.
AUTH_LEVEL_PASSWORD = 1
AUTH_LEVEL_STEP_UP = 2
AUTH_LEVELS: tuple[int, ...] = (AUTH_LEVEL_PASSWORD, AUTH_LEVEL_STEP_UP)

SESSION_REVOKED_LOGOUT = "LOGOUT"
SESSION_REVOKED_ROTATION_REUSE = "ROTATION_REUSE"
SESSION_REVOKED_PASSWORD_CHANGE = "PASSWORD_CHANGE"
SESSION_REVOKED_ADMIN = "ADMIN"
SESSION_REVOKED_DEVICE_RESET = "DEVICE_RESET"
SESSION_REVOKED_SCANNER_REMOVED = "SCANNER_REMOVED"
SESSION_REVOKED_REPLACED = "REPLACED"
SESSION_REVOKED_REASONS: tuple[str, ...] = (
    SESSION_REVOKED_LOGOUT,
    SESSION_REVOKED_ROTATION_REUSE,
    SESSION_REVOKED_PASSWORD_CHANGE,
    SESSION_REVOKED_ADMIN,
    SESSION_REVOKED_DEVICE_RESET,
    SESSION_REVOKED_SCANNER_REMOVED,
    SESSION_REVOKED_REPLACED,
)

# --------------------------------------------------------------------- MFA

MFA_PURPOSE_DEVICE_RESET = "DEVICE_RESET"
MFA_PURPOSE_STEP_UP = "STEP_UP"
MFA_PURPOSE_EMAIL_CHANGE = "EMAIL_CHANGE"
MFA_PURPOSE_PHONE_CHANGE = "PHONE_CHANGE"
MFA_PURPOSE_PASSWORD_RESET = "PASSWORD_RESET"
MFA_PURPOSES: tuple[str, ...] = (
    MFA_PURPOSE_DEVICE_RESET,
    MFA_PURPOSE_STEP_UP,
    MFA_PURPOSE_EMAIL_CHANGE,
    MFA_PURPOSE_PHONE_CHANGE,
    MFA_PURPOSE_PASSWORD_RESET,
)

#: Forgotten-password flow intentionally has a longer lifetime than step-up.
#: The magic link and backup code share exactly this expiration.
PASSWORD_RESET_TTL_MINUTES = 15

#: The code is NEVER stored in plaintext; only its SHA-256 hash is stored.
#: A database CHECK constraint locks this format down, so even direct SQL
#: insertion of a six-digit plaintext code is rejected.
CODE_HASH_PATTERN = r"^[0-9a-f]{64}$"
OTP_MAX_ATTEMPTS = 5
OTP_TTL_MINUTES = 5


#: Minimum signup age. The database migration contains the same value
#: explicitly because already-applied migrations must not be rewritten.
#: Constraint tests verify both definitions remain aligned.
MINIMUM_AGE_YEARS = 16


# ------------------------------------------------------------------ clients
#: Client type declared at login. It determines REFRESH TOKEN TRANSPORT:
#: HttpOnly cookie for web, response body for mobile. The two modes never
#: overlap because a refresh token in the body is readable by JavaScript.
#:
#: The client declares this instead of the server inferring it from User-Agent,
#: which is spoofable and changes across browser versions. A browser claiming
#: to be mobile would weaken only its own transport security, not another
#: user's.
CLIENT_WEB = "web"
CLIENT_MOBILE = "mobile"
CLIENTS: tuple[str, ...] = (CLIENT_WEB, CLIENT_MOBILE)
