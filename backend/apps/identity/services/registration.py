"""
`RegistrationService` — creation d un compte supporter.

Les regles metier vivent ICI, pas dans la vue ni dans le serialiseur. La vue
traduit du HTTP, le serialiseur valide des FORMES ; le service porte les regles
qui doivent tenir quel que soit l appelant — interface web, application mobile,
commande d administration, reprise de donnees.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.exceptions import ValidationBusinessError
from apps.core.outbox.publisher import publish_event

from ..constants import MINIMUM_AGE_YEARS
from ..events import AGGREGATE_USER, USER_REGISTERED, user_registered_payload
from ..exceptions import EmailAlreadyExistsError, TermsNotAcceptedError, UnderageError
from ..models import User

logger = logging.getLogger("fanid.identity")


def age_in_years(birth_date: datetime.date, on_date: datetime.date) -> int:
    """
    Age revolu, calcule sans bibliotheque tierce.

    `(today - birth).days // 365` est faux : il derive d un jour tous les quatre
    ans et fait basculer un utilisateur du bon cote de la limite un jour trop
    tot. La comparaison lexicographique de `(mois, jour)` est exacte, y compris
    pour un 29 fevrier — un natif du 29/02 a son anniversaire le 1er mars les
    annees non bissextiles selon cette regle, ce qui est le choix le plus
    prudent : il attend un jour de plus, jamais l inverse.
    """
    had_birthday = (on_date.month, on_date.day) >= (birth_date.month, birth_date.day)
    return on_date.year - birth_date.year - (0 if had_birthday else 1)


@dataclass(frozen=True, slots=True)
class RegistrationCommand:
    """
    Entree du service, deja validee dans sa FORME par le serialiseur.

    Volontairement fermee : `role`, `is_staff`, `is_superuser` et `is_active`
    n y figurent pas. Le sur-postage n est donc pas « filtre » quelque part — il
    est structurellement impossible d en transporter la valeur jusqu ici. Un
    filtre s oublie lors d un ajout de champ ; une structure fermee, non.

    `terms_accepted` est un BOOLEEN, pas un horodatage. La date d acceptation est
    posee par le SERVEUR : un horodatage fourni par le client serait une preuve
    de consentement fabriquee par la partie qu elle est censee engager.
    """

    email: str
    password: str
    first_name: str
    last_name: str
    date_of_birth: datetime.date
    terms_accepted: bool
    phone: str | None = None


class RegistrationService:
    """Cree un compte supporter et publie l evenement correspondant."""

    @staticmethod
    @transaction.atomic
    def register(command: RegistrationCommand) -> User:
        """
        Cree l utilisateur et publie `identity.user.registered` DANS LA MEME
        TRANSACTION.

        C est l invariant I-5 (ADR-S-03) : `publish_event()` refuse d ailleurs de
        s executer hors transaction. Un evenement emis en dehors pourrait partir
        alors que la creation a ete annulee — un courriel de bienvenue pour un
        compte qui n existe pas.
        """
        if not command.terms_accepted:
            raise TermsNotAcceptedError()

        today = timezone.localdate()
        age = age_in_years(command.date_of_birth, today)
        if age < MINIMUM_AGE_YEARS:
            # `details` ne contient QUE des bornes, jamais la date fournie : le
            # corps d erreur transite dans les journaux et les traces.
            raise UnderageError(details={"minimum_age_years": MINIMUM_AGE_YEARS})

        try:
            # Point de sauvegarde imbrique : sans lui, l `IntegrityError` casse
            # la transaction ENGLOBANTE, et le `publish_event` suivant echouerait
            # avec une erreur incomprehensible au lieu du 400 attendu.
            with transaction.atomic():
                user = User.objects.create_user(
                    email=command.email,
                    password=command.password,
                    date_of_birth=command.date_of_birth,
                    terms_accepted_at=timezone.now(),
                    first_name=command.first_name,
                    last_name=command.last_name,
                    phone=command.phone or None,
                )
        except IntegrityError as exc:
            # Aucune verification prealable par SELECT : entre le SELECT et
            # l INSERT, deux requetes concurrentes passeraient toutes les deux.
            # L unicite `citext` en base est la seule garantie qui tienne ; on
            # traduit sa violation plutot que de courir apres elle.
            raise EmailAlreadyExistsError() from exc
        except DjangoValidationError as exc:
            # `create_user` appelle `full_clean`. Sans ce filet, une violation de
            # validateur de modele remonterait en 500 : DRF ne connait pas
            # `django.core.exceptions.ValidationError`.
            raise ValidationBusinessError(details={"fields": exc.message_dict}) from exc

        publish_event(
            event_type=USER_REGISTERED,
            aggregate_type=AGGREGATE_USER,
            aggregate_id=user.pk,
            actor_id=user.pk,
            payload=user_registered_payload(role_name=user.role.name),
        )

        if str(user.phone or "").strip():
            from ..events import (
                USER_PHONE_CHANGED,
                user_phone_changed_payload,
            )

            publish_event(
                event_type=USER_PHONE_CHANGED,
                aggregate_type=AGGREGATE_USER,
                aggregate_id=user.pk,
                actor_id=user.pk,
                payload=user_phone_changed_payload(
                    first_record=True,
                ),
            )

        # Ni l adresse, ni le mot de passe, ni aucun element du corps de requete.
        # Le `correlation_id` pose par le middleware relie cette ligne a la
        # requete HTTP, qui porte deja ce qu il faut pour enqueter.
        logger.info("identity.user_registered", extra={"user_id": str(user.pk)})
        return user

    @staticmethod
    def as_command(data: dict[str, Any]) -> RegistrationCommand:
        """Construit la commande a partir de donnees deja validees."""
        return RegistrationCommand(
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            date_of_birth=data["date_of_birth"],
            terms_accepted=data["terms_accepted"],
            phone=data.get("phone") or None,
        )
