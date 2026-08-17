#!/usr/bin/env python3
"""
S1-A.8a — Frontiere `organizing -> identity.api` (ADR-S1-05).

    python3 s1a8a.py --check     # verifie les ancres, n ecrit rien
    python3 s1a8a.py             # applique

A lancer depuis `backend/`. Aucune route exposee : ce lot leve la dette
architecturale et debloque la portee `OWN_ORGANIZER`, rien de plus.

La migration n est PAS ecrite ici : `makemigrations organizing` la produit,
et c est la seule facon de satisfaire `makemigrations --check` en CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path.cwd()
MARKER = "class Organizer"


# ===========================================================================
# organizing/constants.py
# ===========================================================================

ORG_CONSTANTS = '''"""
Vocabulaire du contexte `organizing`.

Les valeurs vivent ici, pas dans les modeles : la contrainte `CHECK` de la base
et le code applicatif lisent la MEME source. C est la lecon du doublon de
motifs de revocation, corrige entre S1-A.6e et S1-A.7 — deux enumerations aux
memes valeurs finissent par diverger, et la panne tombe alors sur un chemin
d ecriture.
"""

from __future__ import annotations

from typing import Final

#: Etat de validation d un organisateur (plan S1 §3.1, colonne
#: `validation_status`). Les quatre valeurs sont celles qu impliquent les
#: routes d administration du §3.3 — approuver, rejeter, suspendre — plus
#: l etat initial d une candidature.
#:
#: Les TRANSITIONS entre ces etats ne sont PAS definies ici : elles
#: appartiennent a `OrganizerOnboardingService` (lot S1-A.8b). Ce module ne
#: declare que le vocabulaire.
ORGANIZER_PENDING: Final = "PENDING"
ORGANIZER_APPROVED: Final = "APPROVED"
ORGANIZER_REJECTED: Final = "REJECTED"
ORGANIZER_SUSPENDED: Final = "SUSPENDED"

ORGANIZER_STATUSES: Final[tuple[str, ...]] = (
    ORGANIZER_PENDING,
    ORGANIZER_APPROVED,
    ORGANIZER_REJECTED,
    ORGANIZER_SUSPENDED,
)

#: Longueur maximale du nom commercial. Le plan §3.1 ne la fixe pas ; une
#: colonne `varchar` en exige une. Valeur retenue et consignee comme ecart.
ORG_NAME_MAX_LENGTH: Final = 120
'''


# ===========================================================================
# organizing/querysets.py
# ===========================================================================

ORG_QUERYSETS = '''"""
Gestionnaires du contexte `organizing` (plan S1 §2.5).

Un filtre de perimetre ecrit dans une vue ne protege que cette vue. Ecrit ici,
il devient reutilisable et surtout RELISIBLE : la question « qui voit quoi »
se lit a un seul endroit.
"""

from __future__ import annotations

from typing import Any

from django.db import models

from .constants import ORGANIZER_APPROVED, ORGANIZER_PENDING


class OrganizerQuerySet(models.QuerySet):
    """Filtres de perimetre, nommes d apres le metier et non d apres la colonne."""

    def approved(self) -> "OrganizerQuerySet":
        """Seuls les organisateurs approuves peuvent vendre (RM-1)."""
        return self.filter(validation_status=ORGANIZER_APPROVED)

    def pending(self) -> "OrganizerQuerySet":
        """File d attente de la console d administration."""
        return self.filter(validation_status=ORGANIZER_PENDING)

    def with_user(self) -> "OrganizerQuerySet":
        """
        Charge le compte rattache en une requete.

        La liste d administration affiche l adresse du demandeur : sans cela,
        une page de vingt lignes declenche vingt et une requetes.
        """
        return self.select_related("user")

    def for_user(self, user: Any) -> "OrganizerQuerySet":
        return self.filter(user=user)
'''


# ===========================================================================
# organizing/models.py
# ===========================================================================

ORG_MODELS = '''"""
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
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=DEFAULT_COMMISSION_RATE
    )
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

    objects = OrganizerQuerySet.as_manager()

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
'''


# ===========================================================================
# organizing/permissions.py — c est CE fichier qui porte l import de frontiere
# ===========================================================================

ORG_PERMISSIONS = '''"""
Adaptateurs d autorisation du contexte `organizing`.

**Ce module est le seul point du contexte qui franchit la frontiere.** Il
importe `apps.identity.api`, et rien d autre d `identity` — c est ce que le
contrat `organizing-reaches-identity-through-api-only` verifie a chaque commit
(ADR-S1-05).

Aucune decision n est prise ici. La classe ci-dessous designe la ressource ;
le verdict reste rendu par le moteur d `identity`.
"""

from __future__ import annotations

from typing import Any, ClassVar

from apps.identity.api import OrganizerResourcePermission, Resource


class OrganizerRecordPermission(OrganizerResourcePermission):
    """
    Portee `OWN_ORGANIZER` quand la ressource EST le dossier d organisateur.

    `organizer_lookup = "pk"` parce que l objet ne PORTE pas un organisateur :
    il en est un. Meme raisonnement que `owner_lookup = "pk"` cote `identity`
    pour un point de terminaison dont l objet est l utilisateur.

    `state` est renseigne des maintenant. Aucune portee ne le lit au Sprint 1 —
    `engine._check_scope` ne compare que `organizer_id` — mais le champ existe
    sur `Resource` precisement pour que le lot S1-A.8b y branche les
    transitions sans modifier la signature du moteur.
    """

    organizer_lookup: ClassVar[str] = "pk"

    def get_resource(self, request: Any, view: Any, obj: Any) -> Resource:
        return Resource(
            organizer_id=getattr(obj, self.organizer_lookup, None),
            state=getattr(obj, "validation_status", None),
        )
'''


# ===========================================================================
# organizing/views.py — le mixin d enrichissement, aucune route
# ===========================================================================

ORG_VIEWS = '''"""
Socle de vues du contexte `organizing`.

**Aucune route n est exposee au lot S1-A.8a.** Ce module ne contient que le
mixin qui rend la portee `OWN_ORGANIZER` utilisable ; les six points de
terminaison du plan §3.3 arrivent au lot S1-A.8b.
"""

from __future__ import annotations

from typing import Any

from .models import Organizer


class OrganizerScopedMixin:
    """
    Pose `request.organizer_id` AVANT que DRF ne controle les permissions.

    ## Pourquoi ici, et pas dans `identity`

    `identity` ignore qu `organizing` existe (ADR-S1-05) : c est le sens de
    dependance qui suit le domaine, un compte existant sans organisateur et
    jamais l inverse. `subject_from_request` lit donc un PRIMITIF pose sur la
    requete, exactement comme il lit deja `request.auth_level`.

    ## Pourquoi dans `initial()`

    DRF appelle `initial()` puis, a l interieur, `perform_authentication()` et
    `check_permissions()`. Poser l attribut plus tard — dans `get_object()` ou
    le corps de la vue — arriverait APRES le premier controle de permission.

    Toucher `request.user` ici declenche l authentification : c est exactement
    ce que fait `perform_authentication()` la ligne suivante, donc ni un effet
    de bord ni un cout supplementaire.

    ## Ce qui se passe si on l oublie

    `subject.organizer_id` reste `None`, et `engine._check_scope` refuse avec
    `RESOURCE_ATTRIBUTE_MISSING`. **Le refus vient du moteur, pas d une
    convention** — c est ce qui rend l option B de l ADR sure plutot que
    seulement propre, et un test le fige.
    """

    def initial(self, request: Any, *args: Any, **kwargs: Any) -> None:
        request.organizer_id = self.resolve_organizer_id(request)
        super().initial(request, *args, **kwargs)  # type: ignore[misc]

    @staticmethod
    def resolve_organizer_id(request: Any) -> Any:
        """
        Une requete, dans le contexte proprietaire de la donnee.

        Le cout ne tombe QUE sur les routes de ce contexte, et jamais sur le
        chemin chaud d `identity` — dont l invariant « aucune requete SQL par
        controle d autorisation » reste prouve par `django_assert_num_queries(0)`.
        """
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return None
        return Organizer.objects.filter(user_id=user.pk).values_list("pk", flat=True).first()
'''


# ===========================================================================
# identity/api.py — la frontiere publique
# ===========================================================================

IDENTITY_API = '''"""
Interface publique du contexte `identity` (regle §1.4.3.2, ADR-S1-05).

**Tout ce qui traverse la frontiere passe par ce module, et rien d autre.**
`import-linter` le verifie : `apps.organizing` a interdiction d importer
`apps.identity` sous toute autre forme, avec une exception unique et explicite
pour `apps.identity.api`.

La liste ci-dessous est donc un CONTRAT. Y ajouter un symbole est une decision
d architecture — pas une commodite d ecriture. Un contexte qui a besoin de plus
a probablement besoin d autre chose.

Ce module ne contient AUCUNE logique : il re-expose, et il expose une seule
operation d ecriture, dont le corps tient en une requete.
"""

from __future__ import annotations

import logging
import uuid

from .authz import Action, Resource, Subject, authorize, may_attempt
from .constants import ROLE_IDS, ROLE_ORGANIZER
from .models import User
from .permissions import (
    ActionPermission,
    MethodScopedActionPermission,
    OrganizerResourcePermission,
)

logger = logging.getLogger("fanid.identity")

__all__ = [
    "Action",
    "ActionPermission",
    "MethodScopedActionPermission",
    "OrganizerResourcePermission",
    "Resource",
    "Subject",
    "authorize",
    "grant_organizer_role",
    "may_attempt",
]


def grant_organizer_role(*, user_id: uuid.UUID) -> bool:
    """
    Attribue le role `ORGANIZER` a un compte. Renvoie `True` si une ligne a change.

    **Aucune session n est revoquee, et ce n est pas un oubli.** Le lot S1-A.6a
    a fait de la relecture de session la regle : le serveur lit `user.role_id`
    en base a chaque requete, et le claim `role` du jeton n autorise rien. Le
    changement prend donc effet IMMEDIATEMENT cote serveur. Seul l affichage du
    client reste perime jusqu a son prochain rafraichissement, ce qui est une
    question d interface et non de securite.

    L identifiant du role est resolu depuis la table d UUID figes de
    `constants.py` : aucune requete sur `identity_role`. C est la meme raison
    qui a fait choisir des UUIDv5 deterministes au lot S1-A.1a.
    """
    changed = User.objects.filter(pk=user_id).update(role_id=ROLE_IDS[ROLE_ORGANIZER])
    logger.info("identity.role.granted", extra={"role": ROLE_ORGANIZER, "changed": bool(changed)})
    return bool(changed)
'''


# ===========================================================================
# Tests
# ===========================================================================

TEST_CONTEXT = '''"""
`subject_from_request` — l organisateur vient de la requete, pas d une requete SQL.

Ce fichier fige la moitie `identity` de l option B d ADR-S1-05 : le contexte
lit un primitif pose par la couche exterieure, exactement comme il lit deja
`auth_level`, et refuse tout ce qui n est pas un UUID.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from apps.identity.authz.context import subject_from_request
from apps.identity.constants import ROLE_IDS, ROLE_ORGANIZER

ORG_ID = uuid.uuid4()


def fake_request(**extra):
    user = SimpleNamespace(
        pk=uuid.uuid4(),
        is_authenticated=True,
        is_active=True,
        anonymized_at=None,
        role_id=ROLE_IDS[ROLE_ORGANIZER],
    )
    return SimpleNamespace(user=user, **extra)


def test_the_organizer_is_read_from_the_request():
    subject = subject_from_request(fake_request(organizer_id=ORG_ID))

    assert subject.organizer_id == ORG_ID


def test_an_absent_organizer_gives_none_rather_than_an_error():
    """
    C est le cas d une requete servie par un contexte qui n enrichit pas — la
    quasi-totalite de l API. Le sujet doit se construire normalement, sans
    organisateur.
    """
    subject = subject_from_request(fake_request())

    assert subject.organizer_id is None


@pytest.mark.parametrize("value", ["pas-un-uuid", 42, "", None, object()])
def test_anything_that_is_not_a_uuid_is_ignored(value):
    """
    Meme garde que pour `role_id` : une valeur inattendue ne doit pas lever au
    milieu d un controle d autorisation, elle doit produire l absence de droit.
    """
    subject = subject_from_request(fake_request(organizer_id=value))

    assert subject.organizer_id is None


def test_no_query_is_issued_while_building_the_subject(db, django_assert_num_queries):
    """
    L invariant du lot S1-A.2, preserve. C est la raison pour laquelle
    `resolve_organizer_id()` a ete SUPPRIMEE plutot que remplie : la remplir
    aurait coute une requete par controle d autorisation — sur le chemin le
    plus chaud de l API, et invisible tant qu on ne compte pas.
    """
    with django_assert_num_queries(0):
        subject_from_request(fake_request(organizer_id=ORG_ID))
'''

TEST_ORG_MODEL = '''"""
`Organizer` — les invariants que la BASE fait respecter.

Chaque test tente une insertion INTERDITE et verifie que le SGBD la refuse. Un
invariant verifie seulement par le code applicatif tombe a la premiere commande
d administration ou reprise de donnees.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.identity.models import User
from apps.organizing.constants import ORGANIZER_APPROVED, ORGANIZER_PENDING
from apps.organizing.models import Organizer

pytestmark = pytest.mark.django_db


def make_user(roles, email: str) -> User:
    return User.objects.create_user(
        email=email,
        password="Chataigne-Orageuse-2026",
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1990, 3, 12),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


@pytest.fixture
def applicant(db, roles) -> User:
    return make_user(roles, "organisateur@example.test")


def test_a_new_dossier_starts_pending(applicant):
    organizer = Organizer.objects.create(
        user=applicant, org_name="Stade de France", contact_email="contact@example.test"
    )

    assert organizer.validation_status == ORGANIZER_PENDING
    assert organizer.commission_rate == Decimal("0.0000")


def test_one_account_carries_at_most_one_dossier(applicant):
    """
    Sans cette unicite, l API renverrait une 500 de violation d integrite la ou
    un 403 est la bonne reponse — c est aussi pourquoi `ORGANIZER_CREATE` n est
    pas accorde au role ORGANIZER dans la matrice.
    """
    Organizer.objects.create(user=applicant, org_name="Premier", contact_email="a@example.test")

    with pytest.raises(IntegrityError), transaction.atomic():
        Organizer.objects.create(user=applicant, org_name="Second", contact_email="b@example.test")


def test_the_commercial_name_is_unique_regardless_of_case(applicant, roles):
    """
    « Stade de France » et « stade de france » designent le meme organisateur.
    Une unicite sensible a la casse laisserait creer les deux, et le doublon ne
    se verrait qu au moment ou un acheteur choisit le mauvais.
    """
    Organizer.objects.create(
        user=applicant, org_name="Stade de France", contact_email="a@example.test"
    )
    other = make_user(roles, "second@example.test")

    with pytest.raises(IntegrityError), transaction.atomic():
        Organizer.objects.create(
            user=other, org_name="stade de FRANCE", contact_email="b@example.test"
        )


@pytest.mark.parametrize("rate", [Decimal("-0.0001"), Decimal("1.0001")])
def test_the_commission_rate_stays_between_zero_and_one(applicant, rate):
    with pytest.raises(IntegrityError), transaction.atomic():
        Organizer.objects.create(
            user=applicant,
            org_name="Hors bornes",
            contact_email="a@example.test",
            commission_rate=rate,
        )


def test_an_unknown_status_is_rejected_by_the_database(applicant):
    """
    La contrainte lit le MEME tuple que le code (`constants.py`). Deux
    enumerations aux memes valeurs finissent par diverger — la panne tombe
    alors sur un chemin d ecriture, au pire moment.
    """
    with pytest.raises(IntegrityError), transaction.atomic():
        Organizer.objects.create(
            user=applicant,
            org_name="Etat invente",
            contact_email="a@example.test",
            validation_status="VALIDE",
        )


def test_deleting_an_account_that_carries_a_dossier_is_refused(applicant):
    """
    `PROTECT`, jamais `CASCADE` : supprimer le compte effacerait evenements,
    ventes et journaux de scan. L effacement RGPD passe par l anonymisation.
    """
    Organizer.objects.create(user=applicant, org_name="Protege", contact_email="a@example.test")

    with pytest.raises(IntegrityError), transaction.atomic():
        applicant.delete()


def test_the_querysets_filter_by_business_state(applicant, roles):
    Organizer.objects.create(user=applicant, org_name="En attente", contact_email="a@example.test")
    approved_user = make_user(roles, "approuve@example.test")
    Organizer.objects.create(
        user=approved_user,
        org_name="Approuve",
        contact_email="b@example.test",
        validation_status=ORGANIZER_APPROVED,
    )

    assert Organizer.objects.pending().count() == 1
    assert Organizer.objects.approved().count() == 1
    assert Organizer.objects.for_user(applicant).count() == 1
'''

TEST_BOUNDARY = '''"""
La frontiere `organizing -> identity.api`, et la garantie fail-closed.

Le test qui porte le lot est
`test_forgetting_the_mixin_refuses_instead_of_allowing`. Sans lui, l option B
d ADR-S1-05 ne serait qu une convention : rien ne prouverait qu un oubli
d enrichissement REFUSE au lieu d ouvrir.

Ce fichier appartient a `apps.organizing`. Il ne peut donc importer d
`identity` que `identity.api` — et `import-linter` le verifie. Toute tentative
d y importer `identity.authz` ou `identity.permissions` casserait la CI, ce qui
est exactement l intention.
"""

from __future__ import annotations

import datetime
import uuid
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.identity.api import Action, grant_organizer_role
from apps.identity.models import User
from apps.organizing.constants import ORGANIZER_PENDING
from apps.organizing.models import Organizer
from apps.organizing.permissions import OrganizerRecordPermission
from apps.organizing.views import OrganizerScopedMixin

pytestmark = pytest.mark.django_db


def make_user(roles, email: str, role: str = "ORGANIZER") -> User:
    return User.objects.create_user(
        email=email,
        password="Chataigne-Orageuse-2026",
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1990, 3, 12),
        terms_accepted_at=timezone.now(),
        role=roles[role],
    )


@pytest.fixture
def organizer_user(db, roles) -> User:
    return make_user(roles, "organisateur@example.test")


@pytest.fixture
def dossier(organizer_user) -> Organizer:
    return Organizer.objects.create(
        user=organizer_user, org_name="Stade de France", contact_email="contact@example.test"
    )


def request_for(user, organizer_id=None):
    """Requete minimale : les classes de permission ne lisent que ces attributs."""
    payload = SimpleNamespace(user=user)
    if organizer_id is not None:
        payload.organizer_id = organizer_id
    return payload


VIEW = SimpleNamespace(required_action=Action.ORGANIZER_READ, action=None, policy_actions={})


# ===========================================================================
# La garantie fail-closed
# ===========================================================================


def test_forgetting_the_mixin_refuses_instead_of_allowing(dossier, organizer_user):
    """
    **Le test qui porte le lot.**

    Sans `OrganizerScopedMixin`, la requete ne porte pas `organizer_id`. Le
    sujet se construit avec `organizer_id=None`, et `engine._check_scope`
    refuse avec `RESOURCE_ATTRIBUTE_MISSING`.

    C est ce qui distingue l option B d une convention : l oubli ne produit pas
    un acces ouvert par omission, il produit un refus rendu par le moteur.
    """
    permission = OrganizerRecordPermission()

    granted = permission.has_object_permission(request_for(organizer_user), VIEW, dossier)

    assert granted is False


def test_the_enriched_request_authorizes_the_owner(dossier, organizer_user):
    permission = OrganizerRecordPermission()

    granted = permission.has_object_permission(
        request_for(organizer_user, organizer_id=dossier.pk), VIEW, dossier
    )

    assert granted is True


def test_another_organizer_dossier_is_refused(dossier, organizer_user):
    """Le droit existe, la ressource n est pas la sienne."""
    permission = OrganizerRecordPermission()

    granted = permission.has_object_permission(
        request_for(organizer_user, organizer_id=uuid.uuid4()), VIEW, dossier
    )

    assert granted is False


def test_the_resource_carries_the_state_for_the_next_lot(dossier, organizer_user):
    """
    `Resource.state` est renseigne des maintenant. Aucune portee ne le lit au
    Sprint 1 ; il existe pour que S1-A.8b branche les transitions sans toucher
    a la signature du moteur.
    """
    resource = OrganizerRecordPermission().get_resource(
        request_for(organizer_user), VIEW, dossier
    )

    assert resource.organizer_id == dossier.pk
    assert resource.state == ORGANIZER_PENDING


# ===========================================================================
# Le mixin
# ===========================================================================


def test_the_mixin_resolves_the_dossier_of_the_caller(dossier, organizer_user):
    resolved = OrganizerScopedMixin.resolve_organizer_id(request_for(organizer_user))

    assert resolved == dossier.pk


def test_the_mixin_resolves_nothing_for_an_account_without_dossier(organizer_user):
    assert OrganizerScopedMixin.resolve_organizer_id(request_for(organizer_user)) is None


def test_the_mixin_resolves_nothing_for_an_anonymous_caller():
    anonymous = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))

    assert OrganizerScopedMixin.resolve_organizer_id(anonymous) is None


# ===========================================================================
# L operation publique d `identity`
# ===========================================================================


def test_granting_the_role_takes_effect_in_the_database(roles, db):
    """
    Aucune session n est revoquee : le serveur relit `user.role_id` a chaque
    requete depuis S1-A.6a, donc le changement vaut immediatement.
    """
    fan = make_user(roles, "supporter@example.test", role="FAN")

    assert grant_organizer_role(user_id=fan.pk) is True

    fan.refresh_from_db()
    assert fan.role.name == "ORGANIZER"


def test_granting_the_role_to_an_unknown_account_changes_nothing(db):
    assert grant_organizer_role(user_id=uuid.uuid4()) is False
'''


# ===========================================================================
# .importlinter
# ===========================================================================

CONTEXTS = (
    "apps.identity",
    "apps.organizing",
    "apps.catalog",
    "apps.ordering",
    "apps.payments",
    "apps.ticketing",
    "apps.access",
    "apps.notifying",
    "apps.realtime",
)


def _block(modules: tuple[str, ...]) -> str:
    return "\n".join(f"    {m}" for m in modules)


IMPORTLINTER = f"""[importlinter]
root_package = apps
include_external_packages = True

# Regle absolue (ADR-S-01) : core ne depend d aucun bounded context metier.
[importlinter:contract:core-is-independent]
name = core must not depend on any bounded context
type = forbidden
source_modules =
    apps.core
forbidden_modules =
{_block(CONTEXTS)}

# Les contextes SANS communication synchrone restent mutuellement independants.
# `organizing` en est retire : il porte la premiere dependance synchrone du
# projet, encadree par les deux contrats explicites ci-dessous (ADR-S1-05).
[importlinter:contract:contexts-are-independent]
name = bounded contexts must not import each other directly
type = independence
modules =
{_block(tuple(m for m in CONTEXTS if m != "apps.organizing"))}

# ADR-S1-05 : le sens de la dependance suit le domaine. Un compte existe sans
# organisateur ; l inverse est impossible. `identity` ignore donc totalement
# l existence des autres contextes — contrat PLUS STRICT que l independance
# generique, et c est lui qui garantit l absence de cycle.
[importlinter:contract:identity-is-independent]
name = identity must not depend on any bounded context
type = forbidden
source_modules =
    apps.identity
forbidden_modules =
{_block(tuple(m for m in CONTEXTS if m != "apps.identity"))}

# Liste BLANCHE, pas liste noire : `apps.identity` est interdit en entier,
# descendants compris, et une seule exception est declaree. Un module ajoute
# demain dans `identity` est donc interdit par defaut — ce qui manquait a la
# strategie M-3 de l audit, qui se rabattait sur la revue de code.
#
# `unmatched_ignore_imports_alerting` vaut `error` par defaut : le jour ou plus
# personne n importera `identity.api` depuis `organizing`, cette derogation
# devenue inutile fera echouer la CI au lieu de dormir ici.
[importlinter:contract:organizing-reaches-identity-through-api-only]
name = organizing may only reach identity through its public api
type = forbidden
source_modules =
    apps.organizing
forbidden_modules =
{_block(tuple(m for m in CONTEXTS if m != "apps.organizing"))}
ignore_imports =
    apps.organizing.** -> apps.identity.api
"""


# ===========================================================================
# Application
# ===========================================================================


class Abort(Exception):
    pass


def read(rel: str, base: Path = ROOT) -> str:
    p = base / rel
    if not p.is_file():
        raise Abort(f"fichier introuvable : {rel}  (lancer depuis backend/ ?)")
    return p.read_text(encoding="utf-8")


def swap(src: str, old: str, new: str, rel: str) -> str:
    n = src.count(old)
    if n != 1:
        raise Abort(f"{rel} : ancre vue {n} fois -> {old.strip().splitlines()[0][:66]!r}")
    return src.replace(old, new)


def main() -> int:
    check = "--check" in sys.argv
    edits: list[tuple[Path, str]] = []

    if (ROOT / "apps/identity/api.py").exists():
        raise Abort("apps/identity/api.py existe deja — le lot semble applique.")
    if MARKER in read("apps/organizing/models.py"):
        raise Abort("`class Organizer` existe deja — le lot semble applique.")

    # -- core/http.py --------------------------------------------------------
    http = read("apps/core/http.py")
    anchor = "    auth_level: int\n"
    http = swap(
        http,
        anchor,
        anchor
        + "\n"
        + "    #: Organisateur de rattachement, pose par le contexte proprietaire\n"
        + "    #: avant le controle des permissions (ADR-S1-05). Absent partout\n"
        + "    #: ailleurs : son absence REFUSE la portee `OWN_ORGANIZER`.\n"
        + "    organizer_id: uuid.UUID | None\n",
        "core/http.py",
    )
    edits.append((ROOT / "apps/core/http.py", http))

    # -- identity/authz/context.py -------------------------------------------
    ctx = read("apps/identity/authz/context.py")
    start = ctx.find("def resolve_organizer_id(")
    if start == -1:
        raise Abort("context.py : `resolve_organizer_id` introuvable.")
    end = ctx.find("def subject_from_request(", start)
    if end == -1:
        raise Abort("context.py : `subject_from_request` introuvable.")
    replacement = '''def _organizer_id_from(request: Any) -> uuid.UUID | None:
    """
    Organisateur de rattachement, LU SUR LA REQUETE.

    `identity` ignore qu `organizing` existe (ADR-S1-05) : c est le contexte
    proprietaire qui pose ce primitif avant que DRF ne controle les
    permissions. Le mecanisme est exactement celui d `auth_level`, quelques
    lignes plus bas.

    Le controle de type n est pas une concession au verificateur : une valeur
    inattendue doit produire l ABSENCE de droit, pas une exception au milieu
    d un controle d autorisation. Une requete non enrichie donne donc `None`,
    et le moteur refuse toute portee `OWN_ORGANIZER` avec
    `RESOURCE_ATTRIBUTE_MISSING`.

    Remplace `resolve_organizer_id()`, supprimee au lot S1-A.8a : la remplir
    aurait coute une requete SQL par controle d autorisation, sur le chemin le
    plus chaud de l API.
    """
    value = getattr(request, "organizer_id", None)
    return value if isinstance(value, uuid.UUID) else None


'''
    ctx = ctx[:start] + replacement + ctx[end:]
    ctx = swap(
        ctx,
        "        organizer_id=resolve_organizer_id(user),",
        "        organizer_id=_organizer_id_from(request),",
        "context.py",
    )
    # Motif DISCRIMINANT : la definition et l appel, pas le simple nom — le
    # texte insere cite la fonction supprimee, et un `in` naif s y matcherait
    # lui-meme (lecon S1-A.3 §4.4, enfreinte une fois de trop).
    if "def resolve_organizer_id" in ctx or "resolve_organizer_id(user)" in ctx:
        raise Abort("context.py : la fonction supprimee ou son appel subsistent.")
    edits.append((ROOT / "apps/identity/authz/context.py", ctx))

    # -- test dont la docstring devient fausse -------------------------------
    tap = read("apps/identity/tests/test_authz_permissions.py")
    old_doc = '''    """
    `resolve_organizer_id` renvoie `None` tant que S1-A.8 n existe pas.

    Le refus est donc attendu, et ce test documente le jour ou il changera.
    """'''
    new_doc = '''    """
    La requete ne porte pas d organisateur : le refus est la bonne reponse.

    Depuis le lot S1-A.8a, `organizer_id` n est plus resolu par `identity` mais
    POSE sur la requete par le contexte proprietaire (ADR-S1-05). Une requete
    non enrichie — cas de la quasi-totalite de l API — donne donc un sujet sans
    organisateur, et le moteur refuse avec `RESOURCE_ATTRIBUTE_MISSING`.

    Ce test fige la garantie fail-closed : l oubli d enrichissement REFUSE, il
    n ouvre pas par omission.
    """'''
    tap = swap(tap, old_doc, new_doc, "test_authz_permissions.py")
    edits.append((ROOT / "apps/identity/tests/test_authz_permissions.py", tap))

    # -- fichiers nouveaux ----------------------------------------------------
    new_files = {
        "apps/identity/api.py": IDENTITY_API,
        "apps/organizing/constants.py": ORG_CONSTANTS,
        "apps/organizing/querysets.py": ORG_QUERYSETS,
        "apps/organizing/models.py": ORG_MODELS,
        "apps/organizing/permissions.py": ORG_PERMISSIONS,
        "apps/organizing/views.py": ORG_VIEWS,
        "apps/organizing/tests/__init__.py": "",
        "apps/organizing/tests/test_organizer_model.py": TEST_ORG_MODEL,
        "apps/organizing/tests/test_boundary.py": TEST_BOUNDARY,
        "apps/identity/tests/test_organizer_context.py": TEST_CONTEXT,
    }
    for rel, content in new_files.items():
        target = ROOT / rel
        if rel != "apps/organizing/models.py" and target.exists():
            raise Abort(f"{rel} existe deja — rien n a ete modifie.")
        edits.append((target, content))

    edits.append((ROOT.parent / ".importlinter", IMPORTLINTER))

    if check:
        print("Toutes les ancres correspondent. Aucune ecriture (--check).")
        for path, _ in edits:
            print(f"  serait ecrit : {path}")
        return 0

    (ROOT / "apps/organizing/tests").mkdir(exist_ok=True)
    for path, content in edits:
        path.write_text(content, encoding="utf-8")
        print(f"  ecrit : {path}")

    print(
        "\nS1-A.8a applique.\n\n"
        "  docker compose exec api python manage.py makemigrations organizing\n"
        "  docker compose exec api python manage.py makemigrations --check --dry-run\n"
        "  docker compose exec api black .\n"
        "  docker compose exec api pytest -n auto\n"
        "  isort . && flake8 . && mypy apps/core apps/identity apps/organizing\n"
        "  lint-imports --config=../.importlinter\n"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Abort as e:
        print(f"\nARRET — aucune modification ecrite.\n\n  {e}\n", file=sys.stderr)
        sys.exit(1)
