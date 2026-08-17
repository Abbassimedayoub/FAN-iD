"""
Contexte borne `organizing` — l organisateur et son dossier de validation.

## Ce que ce module N IMPORTE PAS

Ni `apps.identity.models`, ni quoi que ce soit d autre de ce contexte. La cle
etrangere vers le compte passe par `settings.AUTH_USER_MODEL`, une CHAINE que
le registre Django resout paresseusement : aucun import n existe, et le graphe
de dependances reste acyclique (ADR-S1-05).

Consequence honnete a connaitre : `import-linter` ne voit pas ce couplage. La
contrainte de cle etrangere existe bien en base, entre deux contextes. C est
une limite de l outil, pas une faille du modele — mais elle merite d etre
ecrite plutot que decouverte.

## Suppression : PROTECT, jamais CASCADE

`user` est protege : supprimer un compte qui porte un organisateur effacerait
ses evenements, ses ventes et ses journaux de scan. L effacement RGPD passe par
l anonymisation (S5, ADR-13), pas par un `DELETE`.

`validated_by` est en `SET_NULL` : le depart d un administrateur ne doit pas
effacer la trace d une decision, seulement son auteur.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel, UUIDModel, VersionedModel

from .constants import ORG_NAME_MAX_LENGTH, ORGANIZER_PENDING, ORGANIZER_STATUSES
from .querysets import OrganizerQuerySet

#: Taux par defaut. Le plan §3.1 fixe le type `numeric(5,4)` et la contrainte
#: `BETWEEN 0 AND 1`, mais ni valeur par defaut ni qui la renseigne — et
#: `apply` ne peut pas la recevoir du client. Zero est la seule valeur qui
#: n invente aucune regle commerciale : aucune commission tant qu elle n a pas
#: ete posee explicitement. Ecart consigne, a trancher au lot S1-A.8b.
DEFAULT_COMMISSION_RATE = Decimal("0.0000")


class Organizer(UUIDModel, TimeStampedModel, VersionedModel):
    """
    Dossier d organisateur (plan S1 §3.1).

    `VersionedModel` fournit le verrouillage optimiste exige par le plan : deux
    administrateurs validant simultanement le meme dossier ne doivent pas
    s ecraser en silence — le second recoit `409 STALE_RESOURCE`. Le champ est
    pose ici, son EXPLOITATION appartient au lot S1-A.8b.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organizer",
    )
    org_name = models.CharField(max_length=ORG_NAME_MAX_LENGTH)
    validation_status = models.CharField(
        max_length=20,
        default=ORGANIZER_PENDING,
        choices=[(status, status) for status in ORGANIZER_STATUSES],
    )
    commission_rate = models.DecimalField(max_digits=5, decimal_places=4, default=DEFAULT_COMMISSION_RATE)
    vat_number = models.CharField(max_length=32, null=True, blank=True)
    contact_email = models.EmailField(max_length=254)
    rejection_reason = models.TextField(null=True, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizers_validated",
    )

    objects = OrganizerQuerySet.as_manager()  # type: ignore[django-manager-missing]

    class Meta:
        db_table = "organizing_organizer"
        constraints = [
            # Unicite INSENSIBLE A LA CASSE : « Stade de France » et « stade de
            # france » designent le meme organisateur. Une unicite simple
            # laisserait creer les deux, et le doublon ne se verrait qu au
            # moment ou un acheteur choisit le mauvais.
            models.UniqueConstraint(Lower("org_name"), name="uq_organizer_org_name_ci"),
            models.CheckConstraint(
                condition=models.Q(commission_rate__gte=0) & models.Q(commission_rate__lte=1),
                name="ck_organizer_commission_rate_range",
            ),
            models.CheckConstraint(
                condition=models.Q(validation_status__in=list(ORGANIZER_STATUSES)),
                name="ck_organizer_status_valid",
            ),
        ]
        indexes = [
            # Filtre principal de la console d administration (§3.1).
            models.Index(fields=["validation_status"], name="ix_organizer_status"),
        ]

    def __str__(self) -> str:
        return f"{self.org_name} ({self.validation_status})"
