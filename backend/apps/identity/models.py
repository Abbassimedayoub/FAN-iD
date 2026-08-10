"""
Coquille minimale du bounded context `identity` pour le Sprint 0.

§80 master prompt : aucune authentification métier complète, aucun RBAC/ABAC
complet au Sprint 0 — ces éléments arrivent au Sprint 1 (rotation de refresh
token, device fingerprinting, RBAC+ABAC formalisé, cf. Source A §1.5 ADR-S-04).

Ce `User` minimal existe uniquement parce que `AUTH_USER_MODEL` doit pointer
vers un modèle concret dès le premier `migrate`, et parce que la table
`idempotency_record` (prérequis du Sprint 0 lui-même, §3.1 Source B) a une
FK obligatoire vers un utilisateur. Il n'expose et n'implémente RIEN au-delà
du strict socle Django `AbstractUser` + PK UUID (cohérent avec `UUIDModel`,
§16 master prompt) : pas de rôle, pas d'appareil, pas de session, pas de MFA.
Role / Device / Session / MFAChallenge / Organizer sont posés au Sprint 1.
"""
import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        db_table = "identity_user"
