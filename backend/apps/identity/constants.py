"""
Référentiel des rôles (plan S1 §3.1, table `role`).

Les identifiants sont **fixes et dérivés de façon déterministe** (UUIDv5) plutôt
que générés à la volée. Trois raisons :

1. La migration qui ajoute `user.role_id` en NOT NULL a besoin d'une valeur par
   défaut connue à l'écriture de la migration — un UUID tiré au hasard au moment
   du seed ne le permettrait pas.
2. Les identifiants sont identiques en développement, en test, en CI et en
   production : une fixture ou un jeu de données de démonstration reste valide
   partout.
3. Le seed devient réellement idempotent : rejouer la migration ne crée pas de
   doublon sous un nouvel identifiant.

ADR-02 : `Role.permissions` (jsonb) est **descriptif**, affiché dans la console
d'administration. Il n'est JAMAIS la source de vérité de l'autorisation — c'est
le `PolicyEngine`, en code, qui fait foi (master prompt §10).
"""

import uuid

ROLE_FAN = "FAN"
ROLE_ORGANIZER = "ORGANIZER"
ROLE_SCANNER = "SCANNER"
ROLE_ADMIN = "ADMIN"

#: Ordre stable, utilisé par la contrainte CHECK et par les tests de matrice.
ROLE_NAMES: tuple[str, ...] = (ROLE_FAN, ROLE_ORGANIZER, ROLE_SCANNER, ROLE_ADMIN)

#: Rôle attribué à toute inscription publique (master prompt §11 : l'inscription
#: publique ne permet aucune attribution arbitraire de privilège).
DEFAULT_ROLE = ROLE_FAN

ROLE_IDS: dict[str, uuid.UUID] = {
    ROLE_FAN: uuid.UUID("80d63969-f419-5bd6-b682-653e21e74a65"),
    ROLE_ORGANIZER: uuid.UUID("ea173779-0ab3-56b8-9924-23915ef7fc29"),
    ROLE_SCANNER: uuid.UUID("91e56bcb-d23e-5169-a1f3-655e1e44f277"),
    ROLE_ADMIN: uuid.UUID("58d71579-cab7-576e-b233-27c1c424b8bd"),
}


# ---------------------------------------------------------------- appareils

#: Format de l'empreinte d'appareil (master prompt §24).
#: L'empreinte est calculée CÔTÉ CLIENT et reste opaque pour le serveur : il ne
#: la recalcule jamais et n'en déduit rien. Il valide uniquement le format —
#: 64 caractères hexadécimaux MINUSCULES, soit un SHA-256 canonique. Accepter
#: les majuscules créerait deux représentations de la même empreinte, donc deux
#: appareils distincts pour un même téléphone.
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

#: Niveau d'authentification porté par la session et par le JWT (plan S1 §2.4).
#: 1 = mot de passe seul. 2 = vérification renforcée (code reçu par email).
#: Les actions sensibles — réinitialisation d'appareil, changement d'email,
#: suppression de compte — exigent le niveau 2.
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
MFA_PURPOSE_PASSWORD_RESET = "PASSWORD_RESET"
MFA_PURPOSES: tuple[str, ...] = (
    MFA_PURPOSE_DEVICE_RESET,
    MFA_PURPOSE_STEP_UP,
    MFA_PURPOSE_EMAIL_CHANGE,
    MFA_PURPOSE_PASSWORD_RESET,
)

#: Mot de passe oublié : durée volontairement plus longue que le STEP_UP.
#: Le lien magique et le code de secours partagent exactement cette expiration.
PASSWORD_RESET_TTL_MINUTES = 15

#: Le code n'est JAMAIS stocké en clair : seul son SHA-256 l'est (plan S1 §3.1).
#: Ce format est verrouillé par une contrainte CHECK en base — un code à
#: 6 chiffres inséré tel quel y est rejeté, y compris par une écriture SQL
#: directe qui contournerait le service.
CODE_HASH_PATTERN = r"^[0-9a-f]{64}$"
OTP_MAX_ATTEMPTS = 5
OTP_TTL_MINUTES = 5


#: Age minimum a l inscription (RM-13). La contrainte `ck_user_min_age_16` porte
#: la meme valeur en dur dans la migration 0002 : une migration deja appliquee
#: ne se relit pas, on ne peut donc pas l y remplacer par cette constante. Les
#: tests de contrainte de S1-A.1a verifient que les deux disent la meme chose —
#: 16 ans pile accepte, la veille refuse.
MINIMUM_AGE_YEARS = 16


# ------------------------------------------------------------------ clients
#: Type de client declare a la connexion. Il decide du TRANSPORT du jeton de
#: rafraichissement : cookie HttpOnly pour le web, corps de reponse pour le
#: mobile. Les deux ne se cumulent jamais — un refresh present dans le corps est
#: lisible en JavaScript, et le cookie HttpOnly ne protegerait alors plus rien.
#:
#: Declare par le client plutot que devine depuis le `User-Agent` : cet en-tete
#: se falsifie et change a chaque version de navigateur. Un navigateur qui
#: declarerait `mobile` degraderait SA PROPRE securite, celle de personne
#: d autre.
CLIENT_WEB = "web"
CLIENT_MOBILE = "mobile"
CLIENTS: tuple[str, ...] = (CLIENT_WEB, CLIENT_MOBILE)
