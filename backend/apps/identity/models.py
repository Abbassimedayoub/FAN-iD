"""
Bounded context `identity` — Role et User (plan S1 §3.1).

**Point de non-retour** : neuf tables du schéma porteront une clé étrangère vers
`user`. Le modèle est donc figé ici avec ses contraintes, pas ajusté au fil des
sprints.

Ce que ce module NE fait pas : aucune règle métier. L'inscription, la validation
d'âge avec message exploitable, le refus du sur-postage et le consentement CGU
appartiennent à `RegistrationService` (lot S1-A.3). Les modèles ne portent que
les invariants structurels — ceux qui doivent tenir même face à une insertion
SQL directe.
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models

from apps.core.models import TimeStampedModel, VersionedModel

from .constants import ROLE_NAMES
from .fields import CITextEmailField
from .managers import UserManager


class Role(models.Model):
    """
    Référentiel des rôles — 4 lignes, quasi statique (plan S1 §3.1).

    `permissions` est **descriptif** (ADR-02) : il documente les capacités du
    rôle pour la console d'administration. La source de vérité de l'autorisation
    est le `PolicyEngine`, en code (master prompt §10). Ne jamais autoriser une
    requête sur la foi de ce JSON.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=20, unique=True)
    permissions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "identity_role"
        constraints = [
            # Second niveau de défense (ADR-S-04 règle 7) : le SGBD refuse un
            # rôle inconnu même inséré directement en SQL.
            models.CheckConstraint(
                condition=models.Q(name__in=list(ROLE_NAMES)),
                name="ck_role_name_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class User(AbstractUser, TimeStampedModel, VersionedModel):
    """
    Utilisateur — l'email est l'identité canonique de l'application.

    **`username` conservé mais neutralisé** (décision D-4) : `AbstractUser`
    l'impose en `UNIQUE NOT NULL`. Plutôt que de le supprimer — migration
    destructive, contraire au §9 — il devient nullable et non unique. Il ne
    sert plus à rien fonctionnellement ; il est conservé pour ne pas casser
    l'historique de migration et pourra être retiré plus tard en
    expand/contract (ADR-S-08).

    **`date_joined` conservé** pour la même raison. L'horodatage canonique du
    projet est `created_at`, hérité de `TimeStampedModel` comme sur toutes les
    autres tables — c'est lui que référence la contrainte d'âge.

    **Suppression** : jamais de `CASCADE` depuis `user`. Toutes les références
    entrantes seront en `PROTECT` ; l'effacement RGPD passe par l'anonymisation
    (`anonymized_at`, Sprint 5).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # --- Identité ---
    email = CITextEmailField(unique=True)
    username = models.CharField(  # type: ignore[misc]
        max_length=150,
        null=True,
        blank=True,
        validators=[UnicodeUsernameValidator()],
        help_text="Hérité d'AbstractUser, neutralisé : l'identifiant de connexion est l'email.",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="users",
        help_text="V1 : un seul rôle par utilisateur (ADR-01).",
    )

    # --- État civil ---
    date_of_birth = models.DateField()
    phone = models.CharField(max_length=32, null=True, blank=True)

    # --- Conformité ---
    terms_accepted_at = models.DateTimeField()
    anonymized_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    #: `createsuperuser` demandera la date de naissance ; la contrainte d'âge
    #: s'applique aussi aux administrateurs.
    REQUIRED_FIELDS = ["date_of_birth"]

    objects = UserManager()  # type: ignore[misc,assignment]

    class Meta:
        db_table = "identity_user"

    def __str__(self) -> str:
        return self.email
