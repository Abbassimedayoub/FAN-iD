from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from ..constants import (
    ROLE_IDS,
    ROLE_SCANNER,
    SESSION_REVOKED_PASSWORD_CHANGE,
    SESSION_REVOKED_SCANNER_REMOVED,
)
from ..models import User
from .tokens import TokenService

SCANNER_TEMP_PASSWORD_TTL = timedelta(
    minutes=5,
)


def scanner_temporary_password_expires_at():
    return timezone.now() + SCANNER_TEMP_PASSWORD_TTL


def derive_scanner_temporary_password(
    *,
    invitation_id: uuid.UUID,
    generation: int = 1,
) -> str:
    """
    Dérive le secret temporaire sans le stocker
    en clair.

    La génération permet de créer un nouveau
    mot de passe et d'invalider l'ancien.
    """

    if generation < 1:
        raise ValueError("generation must be >= 1")

    digest = salted_hmac(
        "fanid.scanner.temporary-password.v3",
        (f"{invitation_id}:" f"{generation}"),
        algorithm="sha256",
    ).digest()

    lower = "abcdefghjkmnpqrstuvwxyz"
    upper = "ABCDEFGHJKMNPQRSTUVWXYZ"
    digits = "23456789"
    symbols = "!@#$%_-"
    alphabet = lower + upper + digits + symbols

    characters = [
        lower[digest[0] % len(lower)],
        upper[digest[1] % len(upper)],
        digits[digest[2] % len(digits)],
        symbols[digest[3] % len(symbols)],
    ]

    characters.extend(
        alphabet[value % len(alphabet)]
        for value in digest[4:24]
    )

    # Mélange déterministe basé sur le HMAC :
    # le secret reste reconstructible sans stockage en clair,
    # mais aucun préfixe/suffixe visuel n'est constant.
    for index in range(len(characters) - 1, 0, -1):
        swap_index = digest[(index + 7) % len(digest)] % (index + 1)
        characters[index], characters[swap_index] = (
            characters[swap_index],
            characters[index],
        )

    return "".join(characters)


def create_invited_scanner_account(
    *,
    email: str,
    first_name: str,
    last_name: str,
    temporary_password: str,
) -> uuid.UUID:
    """
    Crée un compte SCANNER avec un mot de passe
    temporaire valable cinq minutes.
    """

    user = User(
        email=User.objects.normalize_email(email),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        role_id=ROLE_IDS[ROLE_SCANNER],
        date_of_birth=None,
        terms_accepted_at=None,
        must_change_password=True,
        temporary_password_generation=1,
        temporary_password_expires_at=(scanner_temporary_password_expires_at()),
        is_active=True,
    )

    user.set_password(temporary_password)

    user.full_clean(
        exclude=[
            "password",
        ],
        validate_unique=False,
    )

    user.save()

    return user.pk


def rotate_scanner_temporary_password(
    *,
    user_id: uuid.UUID,
    invitation_id: uuid.UUID,
) -> int:
    """
    Génère une nouvelle génération de secret.

    Le secret précédent devient immédiatement
    invalide grâce au nouveau hash stocké.

    Retourne uniquement le numéro de génération,
    jamais le mot de passe en clair.
    """

    with transaction.atomic():
        user = User.objects.select_for_update().select_related("role").get(pk=user_id)

        if user.role_id != ROLE_IDS[ROLE_SCANNER]:
            raise ValueError("Only SCANNER accounts may " "receive a temporary password.")

        TokenService.revoke_all_for_user(
            user,
            SESSION_REVOKED_PASSWORD_CHANGE,
        )

        generation = (
            max(
                1,
                user.temporary_password_generation,
            )
            + 1
        )

        temporary_password = derive_scanner_temporary_password(
            invitation_id=invitation_id,
            generation=generation,
        )

        user.set_password(temporary_password)

        user.must_change_password = True

        user.temporary_password_generation = generation

        user.temporary_password_used_at = None

        user.temporary_password_expires_at = scanner_temporary_password_expires_at()

        user.save(
            update_fields=[
                "password",
                "must_change_password",
                "temporary_password_generation",
                "temporary_password_used_at",
                "temporary_password_expires_at",
                "updated_at",
            ],
        )

    return generation


def deactivate_scanner_account(
    *,
    user_id: uuid.UUID,
) -> int:
    """
    Désactive et anonymise un compte SCANNER.

    Son historique métier reste conservé et
    l'adresse e-mail initiale peut être réutilisée.
    """

    with transaction.atomic():
        user = User.objects.select_for_update().select_related("role").get(pk=user_id)

        if user.role_id != ROLE_IDS[ROLE_SCANNER]:
            raise ValueError("Only SCANNER accounts may be " "deactivated by this service.")

        revoked = TokenService.revoke_all_for_user(
            user,
            SESSION_REVOKED_SCANNER_REMOVED,
        )

        user.email = f"deleted-scanner-{user.pk}" "@deleted.invalid"

        user.username = None
        user.first_name = ""
        user.last_name = ""
        user.phone = None
        user.date_of_birth = None
        user.terms_accepted_at = None
        user.is_active = False
        user.anonymized_at = timezone.now()
        user.must_change_password = False
        user.temporary_password_used_at = None
        user.temporary_password_expires_at = None

        user.set_unusable_password()

        user.save(
            update_fields=[
                "email",
                "username",
                "first_name",
                "last_name",
                "phone",
                "date_of_birth",
                "terms_accepted_at",
                "is_active",
                "anonymized_at",
                "must_change_password",
                "temporary_password_used_at",
                "temporary_password_expires_at",
                "password",
                "updated_at",
            ],
        )

    return revoked
