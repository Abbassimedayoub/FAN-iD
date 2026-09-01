"""
Matrice d autorisation : 4 roles x 35 actions, autorisation ET refus.

Ce fichier applique la DOUBLE SAISIE. La table `EXPECTED` ci-dessous reecrit en
clair les 96 cellules de la politique, sans reutiliser `POLICY` ni la table
factorisee `_SELF_SERVICE`. Deriver l attendu de l implementation ne prouverait
qu une chose — que le code est egal a lui-meme. Ici, une modification de la
politique fait echouer le test tant qu elle n a pas ete reecrite ici aussi : le
changement devient impossible a passer sans qu un relecteur le voie deux fois.

C est verbeux, et c est le but. Une matrice d autorisation est le genre de
document qu on relit lors d un audit ; elle doit se lire sans executer le code.
"""

from __future__ import annotations

import uuid

import pytest

from apps.identity.authz import (
    POLICY,
    Action,
    Reason,
    Resource,
    Scope,
    Subject,
    authorize,
    may_attempt,
    require_approved_organizer,
)
from apps.identity.authz.decisions import ALLOW, Decision, deny
from apps.identity.constants import (
    AUTH_LEVEL_PASSWORD,
    AUTH_LEVEL_STEP_UP,
    ROLE_ADMIN,
    ROLE_FAN,
    ROLE_ORGANIZER,
    ROLE_SCANNER,
)

ROLES = (ROLE_FAN, ROLE_ORGANIZER, ROLE_SCANNER, ROLE_ADMIN)

#: `None` = refus. Un couple (portee, verification renforcee) = droit accorde.
EXPECTED: dict[tuple[str, Action], tuple[Scope, bool] | None] = {
    # ----------------------------------------------------------------- FAN
    (ROLE_FAN, Action.USER_READ_SELF): (Scope.SELF, False),
    (ROLE_FAN, Action.USER_UPDATE_SELF): (Scope.SELF, False),
    (ROLE_FAN, Action.USER_DELETE_SELF): (Scope.SELF, True),
    (ROLE_FAN, Action.DEVICE_LIST_SELF): (Scope.SELF, False),
    (ROLE_FAN, Action.DEVICE_REVOKE_SELF): (Scope.SELF, True),
    (ROLE_FAN, Action.SESSION_LIST_SELF): (Scope.SELF, False),
    (ROLE_FAN, Action.SESSION_REVOKE_SELF): (Scope.SELF, False),
    (ROLE_FAN, Action.ORGANIZER_CREATE): (Scope.NONE, False),
    (ROLE_FAN, Action.ORGANIZER_READ): None,
    (ROLE_FAN, Action.ORGANIZER_UPDATE): None,
    (ROLE_FAN, Action.ORGANIZER_APPROVE): None,
    (ROLE_FAN, Action.ORGANIZER_REJECT): None,
    (ROLE_FAN, Action.ORGANIZER_SUSPEND): None,
    (ROLE_FAN, Action.SCANNER_INVITE): None,
    (ROLE_FAN, Action.SCANNER_READ): None,
    (ROLE_FAN, Action.SCANNER_REVOKE): None,
    (ROLE_FAN, Action.SCANNER_CREDENTIAL_RESET): None,
    (ROLE_FAN, Action.TICKET_SCAN): None,
    (ROLE_FAN, Action.CATEGORY_READ): None,
    (ROLE_FAN, Action.CATEGORY_CREATE): None,
    (ROLE_FAN, Action.CATEGORY_DELETE): None,
    (ROLE_FAN, Action.EVENT_CREATE): None,
    (ROLE_FAN, Action.EVENT_READ): None,
    (ROLE_FAN, Action.EVENT_UPDATE): None,
    (ROLE_FAN, Action.EVENT_DELETE): None,
    (ROLE_FAN, Action.EVENT_PUBLISH): None,
    (ROLE_FAN, Action.EVENT_ARCHIVE): None,
    (ROLE_FAN, Action.EVENT_UNARCHIVE): None,
    (ROLE_FAN, Action.EVENT_POSTPONE): None,
    (ROLE_FAN, Action.EVENT_SUSPEND): None,
    (ROLE_FAN, Action.EVENT_CANCEL): None,
    (ROLE_FAN, Action.TICKET_CATEGORY_CREATE): None,
    (ROLE_FAN, Action.TICKET_CATEGORY_READ): None,
    (ROLE_FAN, Action.TICKET_CATEGORY_UPDATE): None,
    (ROLE_FAN, Action.TICKET_CATEGORY_DELETE): None,
    # ----------------------------------------------------------- ORGANIZER
    (ROLE_ORGANIZER, Action.USER_READ_SELF): (Scope.SELF, False),
    (ROLE_ORGANIZER, Action.USER_UPDATE_SELF): (Scope.SELF, False),
    (ROLE_ORGANIZER, Action.USER_DELETE_SELF): (Scope.SELF, True),
    (ROLE_ORGANIZER, Action.DEVICE_LIST_SELF): (Scope.SELF, False),
    (ROLE_ORGANIZER, Action.DEVICE_REVOKE_SELF): (Scope.SELF, True),
    (ROLE_ORGANIZER, Action.SESSION_LIST_SELF): (Scope.SELF, False),
    (ROLE_ORGANIZER, Action.SESSION_REVOKE_SELF): (Scope.SELF, False),
    # Un compte ne porte qu un seul organisateur.
    (ROLE_ORGANIZER, Action.ORGANIZER_CREATE): None,
    (ROLE_ORGANIZER, Action.ORGANIZER_READ): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.ORGANIZER_UPDATE): (Scope.OWN_ORGANIZER, False),
    # On ne modere pas son propre dossier.
    (ROLE_ORGANIZER, Action.ORGANIZER_APPROVE): None,
    (ROLE_ORGANIZER, Action.ORGANIZER_REJECT): None,
    (ROLE_ORGANIZER, Action.ORGANIZER_SUSPEND): None,
    (ROLE_ORGANIZER, Action.SCANNER_INVITE): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.SCANNER_READ): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.SCANNER_REVOKE): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.SCANNER_CREDENTIAL_RESET): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.TICKET_SCAN): None,
    (ROLE_ORGANIZER, Action.CATEGORY_READ): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.CATEGORY_CREATE): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.CATEGORY_DELETE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_CREATE): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.EVENT_READ): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_UPDATE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_DELETE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_PUBLISH): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_ARCHIVE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_UNARCHIVE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_POSTPONE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_SUSPEND): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_CANCEL): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.TICKET_CATEGORY_CREATE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.TICKET_CATEGORY_READ): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.TICKET_CATEGORY_UPDATE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.TICKET_CATEGORY_DELETE): (Scope.OWN_ORGANIZER, False),
    # ------------------------------------------------------------- SCANNER
    (ROLE_SCANNER, Action.USER_READ_SELF): (Scope.SELF, False),
    (ROLE_SCANNER, Action.USER_UPDATE_SELF): (Scope.SELF, False),
    (ROLE_SCANNER, Action.USER_DELETE_SELF): (Scope.SELF, True),
    (ROLE_SCANNER, Action.DEVICE_LIST_SELF): (Scope.SELF, False),
    (ROLE_SCANNER, Action.DEVICE_REVOKE_SELF): (Scope.SELF, True),
    (ROLE_SCANNER, Action.SESSION_LIST_SELF): (Scope.SELF, False),
    (ROLE_SCANNER, Action.SESSION_REVOKE_SELF): (Scope.SELF, False),
    (ROLE_SCANNER, Action.ORGANIZER_CREATE): None,
    (ROLE_SCANNER, Action.ORGANIZER_READ): (Scope.OWN_ORGANIZER, False),
    (ROLE_SCANNER, Action.ORGANIZER_UPDATE): None,
    (ROLE_SCANNER, Action.ORGANIZER_APPROVE): None,
    (ROLE_SCANNER, Action.ORGANIZER_REJECT): None,
    (ROLE_SCANNER, Action.ORGANIZER_SUSPEND): None,
    (ROLE_SCANNER, Action.SCANNER_INVITE): None,
    (ROLE_SCANNER, Action.SCANNER_READ): None,
    (ROLE_SCANNER, Action.SCANNER_REVOKE): None,
    (ROLE_SCANNER, Action.SCANNER_CREDENTIAL_RESET): None,
    (ROLE_SCANNER, Action.TICKET_SCAN): (Scope.OWN_ORGANIZER, False),
    (ROLE_SCANNER, Action.CATEGORY_READ): None,
    (ROLE_SCANNER, Action.CATEGORY_CREATE): None,
    (ROLE_SCANNER, Action.CATEGORY_DELETE): None,
    (ROLE_SCANNER, Action.EVENT_CREATE): None,
    (ROLE_SCANNER, Action.EVENT_READ): None,
    (ROLE_SCANNER, Action.EVENT_UPDATE): None,
    (ROLE_SCANNER, Action.EVENT_DELETE): None,
    (ROLE_SCANNER, Action.EVENT_PUBLISH): None,
    (ROLE_SCANNER, Action.EVENT_ARCHIVE): None,
    (ROLE_SCANNER, Action.EVENT_UNARCHIVE): None,
    (ROLE_SCANNER, Action.EVENT_POSTPONE): None,
    (ROLE_SCANNER, Action.EVENT_SUSPEND): None,
    (ROLE_SCANNER, Action.EVENT_CANCEL): None,
    (ROLE_SCANNER, Action.TICKET_CATEGORY_CREATE): None,
    (ROLE_SCANNER, Action.TICKET_CATEGORY_READ): None,
    (ROLE_SCANNER, Action.TICKET_CATEGORY_UPDATE): None,
    (ROLE_SCANNER, Action.TICKET_CATEGORY_DELETE): None,
    # --------------------------------------------------------------- ADMIN
    (ROLE_ADMIN, Action.USER_READ_SELF): (Scope.SELF, False),
    (ROLE_ADMIN, Action.USER_UPDATE_SELF): (Scope.SELF, False),
    (ROLE_ADMIN, Action.USER_DELETE_SELF): (Scope.SELF, True),
    (ROLE_ADMIN, Action.DEVICE_LIST_SELF): (Scope.SELF, False),
    (ROLE_ADMIN, Action.DEVICE_REVOKE_SELF): (Scope.SELF, True),
    (ROLE_ADMIN, Action.SESSION_LIST_SELF): (Scope.SELF, False),
    (ROLE_ADMIN, Action.SESSION_REVOKE_SELF): (Scope.SELF, False),
    (ROLE_ADMIN, Action.ORGANIZER_CREATE): None,
    (ROLE_ADMIN, Action.ORGANIZER_READ): (Scope.ANY, False),
    (ROLE_ADMIN, Action.ORGANIZER_UPDATE): (Scope.ANY, False),
    (ROLE_ADMIN, Action.ORGANIZER_APPROVE): (Scope.ANY, True),
    (ROLE_ADMIN, Action.ORGANIZER_REJECT): (Scope.ANY, True),
    (ROLE_ADMIN, Action.ORGANIZER_SUSPEND): (Scope.ANY, True),
    (ROLE_ADMIN, Action.SCANNER_INVITE): None,
    (ROLE_ADMIN, Action.SCANNER_READ): None,
    (ROLE_ADMIN, Action.SCANNER_REVOKE): None,
    (ROLE_ADMIN, Action.SCANNER_CREDENTIAL_RESET): None,
    # Separation des fonctions : administrer n est pas scanner.
    (ROLE_ADMIN, Action.TICKET_SCAN): None,
    (ROLE_ADMIN, Action.CATEGORY_READ): None,
    (ROLE_ADMIN, Action.CATEGORY_CREATE): None,
    (ROLE_ADMIN, Action.CATEGORY_DELETE): None,
    (ROLE_ADMIN, Action.EVENT_CREATE): None,
    (ROLE_ADMIN, Action.EVENT_READ): None,
    (ROLE_ADMIN, Action.EVENT_UPDATE): None,
    (ROLE_ADMIN, Action.EVENT_DELETE): None,
    (ROLE_ADMIN, Action.EVENT_PUBLISH): None,
    (ROLE_ADMIN, Action.EVENT_ARCHIVE): None,
    (ROLE_ADMIN, Action.EVENT_UNARCHIVE): None,
    (ROLE_ADMIN, Action.EVENT_POSTPONE): None,
    (ROLE_ADMIN, Action.EVENT_SUSPEND): None,
    (ROLE_ADMIN, Action.EVENT_CANCEL): None,
    (ROLE_ADMIN, Action.TICKET_CATEGORY_CREATE): None,
    (ROLE_ADMIN, Action.TICKET_CATEGORY_READ): None,
    (ROLE_ADMIN, Action.TICKET_CATEGORY_UPDATE): None,
    (ROLE_ADMIN, Action.TICKET_CATEGORY_DELETE): None,
}

ALL_CELLS = [(role, action) for role in ROLES for action in Action]


# ===========================================================================
# 1. La matrice couvre tout le catalogue
# ===========================================================================


def test_the_expected_matrix_covers_every_role_and_every_action():
    """
    Ajouter une action ou un role sans decider de sa politique doit echouer ici.

    C est la garantie qui transforme cette table en preuve : sans elle, une
    treiziemme action pourrait exister, n etre accordee a personne par oubli —
    ou pire, etre accordee sans que personne l ait ecrit noir sur blanc.
    """
    assert set(EXPECTED) == set(ALL_CELLS)
    assert len(ALL_CELLS) == 140, "4 roles x 35 actions"


@pytest.mark.parametrize(("role", "action"), ALL_CELLS)
def test_policy_matches_the_declared_matrix(role: str, action: Action):
    """Chaque cellule de la politique est conforme a la table ci-dessus."""
    grant = POLICY[role].get(action)
    expected = EXPECTED[(role, action)]

    if expected is None:
        assert grant is None, f"{role} ne devrait PAS avoir {action}"
        return

    scope, step_up = expected
    assert grant is not None, f"{role} devrait avoir {action}"
    assert grant.scope is scope
    assert grant.step_up is step_up


# ===========================================================================
# 2. Le moteur applique la matrice — autorisation ET refus
# ===========================================================================

USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
ORG_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
OTHER_ORG_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")


def _subject(role: str, *, step_up: bool = True) -> Subject:
    """Sujet nominal : actif, proprietaire, verifie. Tout doit passer."""
    return Subject(
        user_id=USER_ID,
        role=role,
        is_active=True,
        auth_level=AUTH_LEVEL_STEP_UP if step_up else AUTH_LEVEL_PASSWORD,
        organizer_id=ORG_ID,
    )


#: Ressource qui satisfait toutes les portees a la fois.
OWNED = Resource(owner_id=USER_ID, organizer_id=ORG_ID)
#: Ressource d autrui, sur les deux axes.
FOREIGN = Resource(owner_id=OTHER_USER_ID, organizer_id=OTHER_ORG_ID)


@pytest.mark.parametrize(("role", "action"), ALL_CELLS)
def test_engine_grants_exactly_what_the_matrix_declares(role: str, action: Action):
    """
    Sujet ideal, ressource lui appartenant : seules les cellules accordees
    passent. C est la moitie « autorisation » de l exigence.
    """
    decision = authorize(_subject(role), action, OWNED)
    assert decision.allowed is (EXPECTED[(role, action)] is not None), decision.reason


@pytest.mark.parametrize(("role", "action"), ALL_CELLS)
def test_engine_refuses_every_action_on_a_resource_owned_by_someone_else(role: str, action: Action):
    """
    Moitie « refus » : la meme matrice, sur la ressource d autrui.

    Seules restent autorisees les cellules dont la portee est explicitement
    `NONE` (aucune instance) ou `ANY` (supervision assumee). Toute autre
    autorisation signalerait une fuite ABAC — le defaut ou le controle de role
    passe mais le controle d appartenance est oublie.
    """
    decision = authorize(_subject(role), action, FOREIGN)
    expected = EXPECTED[(role, action)]
    should_pass = expected is not None and expected[0] in (Scope.NONE, Scope.ANY)
    assert decision.allowed is should_pass, decision.reason


@pytest.mark.parametrize(("role", "action"), ALL_CELLS)
def test_step_up_actions_are_refused_to_a_password_only_session(role: str, action: Action):
    """Sans verification renforcee, les actions irreversibles tombent."""
    decision = authorize(_subject(role, step_up=False), action, OWNED)
    expected = EXPECTED[(role, action)]
    should_pass = expected is not None and not expected[1]
    assert decision.allowed is should_pass, decision.reason
    if expected is not None and expected[1]:
        assert decision.reason is Reason.STEP_UP_REQUIRED


# ===========================================================================
# 3. Les refus structurels
# ===========================================================================


@pytest.mark.parametrize("action", list(Action))
def test_an_anonymous_subject_is_refused_everything(action: Action):
    from apps.identity.authz import ANONYMOUS

    decision = authorize(ANONYMOUS, action, OWNED)
    assert decision.allowed is False
    assert decision.reason is Reason.UNAUTHENTICATED


@pytest.mark.parametrize("action", list(Action))
def test_a_deactivated_subject_loses_every_right_including_over_itself(action: Action):
    """
    Un compte anonymise (RGPD) ou desactive ne conserve AUCUN droit.

    Y compris `USER_READ_SELF` : apres anonymisation il n y a plus de « soi »
    a lire. Faire une exception pour les actions sur soi-meme laisserait un
    compte suspendu consulter et modifier ses donnees.
    """
    subject = Subject(user_id=USER_ID, role=ROLE_ADMIN, is_active=False, auth_level=AUTH_LEVEL_STEP_UP)
    decision = authorize(subject, action, OWNED)
    assert decision.allowed is False
    assert decision.reason is Reason.INACTIVE_SUBJECT


def test_an_unknown_role_obtains_nothing():
    """Un role present en base mais absent du code n herite d aucun droit."""
    subject = Subject(user_id=USER_ID, role="SUPERUSER", is_active=True, auth_level=AUTH_LEVEL_STEP_UP)
    decision = authorize(subject, Action.USER_READ_SELF, OWNED)
    assert decision.allowed is False
    assert decision.reason is Reason.UNKNOWN_ROLE


def test_an_action_outside_the_catalogue_is_refused_and_named_as_such():
    """Une chaine libre ne doit pas se confondre avec une politique trop stricte."""
    decision = authorize(_subject(ROLE_ADMIN), "identity:user:read_slef", OWNED)  # type: ignore[arg-type]
    assert decision.allowed is False
    assert decision.reason is Reason.UNKNOWN_ACTION


def test_a_scoped_action_without_any_resource_is_refused():
    """
    Fail-closed : portee liee a une instance, aucune instance fournie => refus.

    C est le cas d une vue de detail qui n aurait pas appele `get_object()`.
    L erreur la plus repandue des systemes ABAC est d interpreter l absence de
    donnee comme une absence de restriction.
    """
    decision = authorize(_subject(ROLE_FAN), Action.USER_READ_SELF, None)
    assert decision.allowed is False
    assert decision.reason is Reason.RESOURCE_ATTRIBUTE_MISSING


def test_a_resource_missing_the_attribute_the_rule_needs_is_refused():
    decision = authorize(_subject(ROLE_ORGANIZER), Action.ORGANIZER_READ, Resource(owner_id=USER_ID))
    assert decision.allowed is False
    assert decision.reason is Reason.RESOURCE_ATTRIBUTE_MISSING


def test_a_subject_without_organizer_cannot_reach_an_organizer_scoped_resource():
    """Un scanner detache de tout organisateur ne scanne rien."""
    subject = Subject(user_id=USER_ID, role=ROLE_SCANNER, is_active=True, auth_level=AUTH_LEVEL_STEP_UP)
    decision = authorize(subject, Action.TICKET_SCAN, Resource(organizer_id=ORG_ID))
    assert decision.allowed is False
    assert decision.reason is Reason.RESOURCE_ATTRIBUTE_MISSING


# ===========================================================================
# 4. L ordre des controles ne doit rien divulguer
# ===========================================================================


def test_ownership_is_checked_before_step_up_so_that_a_stranger_learns_nothing():
    """
    Un non-proprietaire recoit `NOT_OWNER`, jamais `STEP_UP_REQUIRED`.

    Dans l ordre inverse, la reponse apprendrait a l attaquant que l action lui
    serait accordee sur sa propre ressource — et, sur un identifiant devine, que
    la ressource visee existe. Meme raisonnement que le refus d exposer
    `DEVICE_LOCKED` avant d avoir prouve le mot de passe (§ Authentification).
    """
    subject = Subject(user_id=USER_ID, role=ROLE_FAN, is_active=True, auth_level=AUTH_LEVEL_PASSWORD)
    decision = authorize(subject, Action.DEVICE_REVOKE_SELF, Resource(owner_id=OTHER_USER_ID))
    assert decision.allowed is False
    assert decision.reason is Reason.NOT_OWNER


def test_an_inactive_subject_is_named_inactive_before_any_role_check():
    """Un compte suspendu au role inconnu reste d abord un compte suspendu."""
    subject = Subject(user_id=USER_ID, role="SUPERUSER", is_active=False)
    assert authorize(subject, Action.USER_READ_SELF, OWNED).reason is Reason.INACTIVE_SUBJECT


# ===========================================================================
# 5. Proprietes structurelles de la politique
# ===========================================================================


def test_the_policy_table_cannot_be_modified_at_runtime():
    """
    Une politique modifiable a chaud est une politique non auditable.

    `MappingProxyType` fait echouer toute tentative d ecriture — y compris celle
    d un test qui voudrait « juste » accorder un droit temporairement, ce qui
    contaminerait tous les tests suivants sous `pytest -n auto`.
    """
    with pytest.raises(TypeError):
        POLICY[ROLE_FAN][Action.ORGANIZER_APPROVE] = None  # type: ignore[index]
    with pytest.raises(TypeError):
        POLICY["ROOT"] = {}  # type: ignore[index]


def test_only_the_admin_role_holds_an_unscoped_grant():
    """
    Une portee `ANY` contourne l ABAC : elle doit rester une exception visible.

    Ce test echoue des qu une portee `ANY` apparait ailleurs, ce qui force a
    justifier l elargissement plutot qu a le laisser passer dans un diff.
    """
    unscoped = {
        (role, action)
        for role, grants in POLICY.items()
        for action, grant in grants.items()
        if grant.scope is Scope.ANY
    }
    assert {role for role, _ in unscoped} == {ROLE_ADMIN}


def test_every_irreversible_action_requires_step_up():
    """
    Verrou de conception : suppression de compte, revocation d appareil et
    validation d organisateur exigent une verification renforcee, pour tous les
    roles. Ajouter un droit sans `step_up` sur l une d elles fait echouer ici.
    """
    irreversible = {Action.USER_DELETE_SELF, Action.DEVICE_REVOKE_SELF, Action.ORGANIZER_APPROVE}
    for role, grants in POLICY.items():
        for action in irreversible & set(grants):
            assert grants[action].step_up is True, f"{role} / {action} sans verification renforcee"


# ===========================================================================
# 6. Pre-requis d approbation organisateur
# ===========================================================================


def test_pending_organizer_is_refused_by_the_approval_gate():
    subject = Subject(
        user_id=USER_ID,
        role=ROLE_ORGANIZER,
        is_active=True,
        auth_level=AUTH_LEVEL_STEP_UP,
        organizer_id=ORG_ID,
        organizer_is_approved=False,
    )

    decision = require_approved_organizer(subject)

    assert decision.allowed is False
    assert decision.reason is Reason.ORGANIZER_NOT_APPROVED


def test_approved_organizer_passes_the_approval_gate():
    subject = Subject(
        user_id=USER_ID,
        role=ROLE_ORGANIZER,
        is_active=True,
        auth_level=AUTH_LEVEL_STEP_UP,
        organizer_id=ORG_ID,
        organizer_is_approved=True,
    )

    assert require_approved_organizer(subject) is ALLOW


def test_non_organizer_cannot_pass_the_gate_even_with_a_true_primitive():
    subject = Subject(
        user_id=USER_ID,
        role=ROLE_FAN,
        is_active=True,
        auth_level=AUTH_LEVEL_STEP_UP,
        organizer_is_approved=True,
    )

    decision = require_approved_organizer(subject)

    assert decision.allowed is False
    assert decision.reason is Reason.ROLE_NOT_GRANTED


# ===========================================================================
# 7. Le pre-controle RBAC et le garde-fou du verdict
# ===========================================================================


def test_may_attempt_ignores_ownership_and_must_never_be_used_alone():
    """
    `may_attempt` accepte la ressource d autrui — c est sa definition.

    Ce test existe pour figer cette faiblesse par ecrit : si quelqu un
    « corrige » un jour `may_attempt` pour verifier l appartenance, il devra
    d abord expliquer pourquoi le pre-controle de DRF, appele avant le
    chargement de l objet, aurait acces a cet objet.
    """
    subject = Subject(user_id=USER_ID, role=ROLE_FAN, is_active=True, auth_level=AUTH_LEVEL_STEP_UP)
    assert may_attempt(subject, Action.USER_READ_SELF).allowed is True
    assert authorize(subject, Action.USER_READ_SELF, FOREIGN).allowed is False


@pytest.mark.parametrize(("role", "action"), ALL_CELLS)
def test_may_attempt_enforces_step_up_even_without_any_resource(role: str, action: Action):
    """
    Sans ce controle, une action renforcee dont la vue ne charge AUCUN objet —
    `ORGANIZER_APPROVE` — passerait sans preuve d identite fraiche : le
    pre-controle l accepterait et `has_object_permission` ne serait jamais
    appele. Le verrou existerait dans le moteur sans jamais etre atteint.
    """
    expected = EXPECTED[(role, action)]
    decision = may_attempt(_subject(role, step_up=False), action)
    assert decision.allowed is (expected is not None and not expected[1]), decision.reason
    if expected is not None and expected[1]:
        assert decision.reason is Reason.STEP_UP_REQUIRED


def test_may_attempt_still_refuses_an_action_the_role_never_holds():
    subject = Subject(user_id=USER_ID, role=ROLE_FAN, is_active=True, auth_level=AUTH_LEVEL_STEP_UP)
    decision = may_attempt(subject, Action.ORGANIZER_APPROVE)
    assert decision.allowed is False
    assert decision.reason is Reason.ROLE_NOT_GRANTED


def test_a_decision_cannot_be_evaluated_as_a_boolean():
    """`if decision:` serait toujours vrai : on prefere une panne bruyante."""
    with pytest.raises(TypeError, match="decision.allowed"):
        bool(ALLOW)


def test_a_decision_cannot_be_built_with_an_incoherent_reason():
    with pytest.raises(ValueError):
        Decision(allowed=True, reason=Reason.NOT_OWNER)
    with pytest.raises(ValueError):
        Decision(allowed=False, reason=Reason.ALLOWED)
    with pytest.raises(ValueError):
        deny(Reason.ALLOWED)


def test_the_subject_is_immutable():
    """Empeche une escalade de privileges par mutation apres decision."""
    subject = _subject(ROLE_FAN)
    with pytest.raises(AttributeError):
        subject.role = ROLE_ADMIN  # type: ignore[misc]
