"""
Le moteur de decision. Point unique d autorisation du systeme.

Aucune autre partie du code ne doit comparer un role a une chaine, ni tester
`user.is_staff`, ni verifier une appartenance a la main. Un `if role == "ADMIN"`
egare dans une vue est une regle invisible depuis la politique, donc une regle
qui ne sera ni relue, ni testee, ni retiree le jour ou elle devient fausse. Le
contrat `flake8`/revue de code est simple : hors de ce paquet, on appelle
`authorize()`.

Le moteur est une fonction PURE : memes entrees, meme verdict, aucun acces base,
aucune horloge, aucun aleatoire. C est ce qui rend la matrice exhaustive
(4 roles x 14 actions, autorisation ET refus) executable en quelques
millisecondes — et donc reellement exhaustive plutot que sondee.
"""

from __future__ import annotations

from ..constants import AUTH_LEVEL_STEP_UP, ROLE_ORGANIZER
from .actions import Action
from .decisions import ALLOW, Decision, Reason, deny
from .rules import POLICY, Grant, Scope
from .subject import Resource, Subject


def authorize(subject: Subject, action: Action, resource: Resource | None = None) -> Decision:
    """
    Repond a « ce sujet peut-il executer cette action sur cette ressource ? ».

    L ORDRE des controles est un choix de securite, pas une commodite :

    1. authentification, 2. etat du compte, 3. role connu, 4. action connue,
    5. droit du role (RBAC), 6. appartenance de la ressource (ABAC),
    7. niveau d authentification.

    L appartenance (6) est verifiee AVANT la verification renforcee (7). Dans
    l ordre inverse, un sujet non proprietaire recevrait `STEP_UP_REQUIRED`, ce
    qui lui apprendrait que l action lui serait accordee sur SA ressource — et,
    sur une ressource devinee, que celle-ci existe. C est la meme regle que pour
    l authentification : ne jamais reveler l etat d une ressource avant d avoir
    prouve le droit d en connaitre l existence.
    """
    if not subject.is_authenticated:
        return deny(Reason.UNAUTHENTICATED)

    # Un compte desactive ou anonymise (RGPD) perd TOUT droit, y compris sur
    # ses propres donnees : le sens d une anonymisation est qu il n y a plus
    # personne pour les lire.
    if not subject.is_active:
        return deny(Reason.INACTIVE_SUBJECT)

    grants = POLICY.get(subject.role or "")
    if grants is None:
        return deny(Reason.UNKNOWN_ROLE)

    # `action` est type `Action`, mais rien n empeche un appelant non type de
    # passer une chaine libre. Le controle explicite evite qu une faute de
    # frappe se transforme en `ROLE_NOT_GRANTED` — un motif qui laisserait
    # croire a une politique trop stricte plutot qu a un bug d appel.
    if not isinstance(action, Action):
        return deny(Reason.UNKNOWN_ACTION)

    grant = grants.get(action)
    if grant is None:
        return deny(Reason.ROLE_NOT_GRANTED)

    scope_decision = _check_scope(subject, grant, resource)
    if not scope_decision.allowed:
        return scope_decision

    if grant.step_up and subject.auth_level < AUTH_LEVEL_STEP_UP:
        return deny(Reason.STEP_UP_REQUIRED)

    return ALLOW


def require_approved_organizer(subject: Subject) -> Decision:
    """
    Verifie le pre-requis actor-level `ORGANIZER_APPROVED`.

    Cette regle ne porte sur aucune ressource et ne remplace pas RBAC/ABAC.
    Une future ecriture metier doit donc composer sa permission d action avec
    `IsApprovedOrganizer`.

    L etat est un primitif deja pose sur la requete par le contexte proprietaire
    `organizing` : ce moteur reste pur et ne touche jamais la base.
    """
    if not subject.is_authenticated:
        return deny(Reason.UNAUTHENTICATED)

    if not subject.is_active:
        return deny(Reason.INACTIVE_SUBJECT)

    if (subject.role or "") not in POLICY:
        return deny(Reason.UNKNOWN_ROLE)

    if subject.role != ROLE_ORGANIZER:
        return deny(Reason.ROLE_NOT_GRANTED)

    if not subject.organizer_is_approved:
        return deny(Reason.ORGANIZER_NOT_APPROVED)

    return ALLOW


def _check_scope(subject: Subject, grant: Grant, resource: Resource | None) -> Decision:
    """Couche ABAC : le droit du role s exerce-t-il sur CETTE instance ?"""
    if grant.scope is Scope.NONE or grant.scope is Scope.ANY:
        # Aucune instance a verifier. Une ressource fournie est ignoree, elle
        # ne peut donc pas elargir le droit.
        return ALLOW

    if resource is None:
        # Portee liee a une instance, mais aucune instance fournie : refus.
        # C est le cas d une vue de detail qui aurait oublie d appeler
        # `get_object()`. Autoriser ici serait le defaut le plus courant des
        # systemes ABAC — l absence de donnee interpretee comme absence de
        # restriction.
        return deny(Reason.RESOURCE_ATTRIBUTE_MISSING)

    if grant.scope is Scope.SELF:
        if resource.owner_id is None:
            return deny(Reason.RESOURCE_ATTRIBUTE_MISSING)
        return ALLOW if resource.owner_id == subject.user_id else deny(Reason.NOT_OWNER)

    if grant.scope is Scope.OWN_ORGANIZER:
        if resource.organizer_id is None or subject.organizer_id is None:
            return deny(Reason.RESOURCE_ATTRIBUTE_MISSING)
        return ALLOW if resource.organizer_id == subject.organizer_id else deny(Reason.NOT_OWNER)

    # Portee ajoutee a `Scope` sans traitement ici : on refuse. Le defaut d un
    # `match` incomplet doit etre le refus, jamais l acceptation.
    return deny(Reason.ROLE_NOT_GRANTED)


def may_attempt(subject: Subject, action: Action) -> Decision:
    """
    Pre-controle SANS verification d appartenance.

    Utilise par `has_permission` de DRF, appele avant que la vue ait charge
    l objet. Il repond a « ce role peut-il un jour faire cela, et ce sujet
    a-t-il le niveau d authentification exige ? ».

    La verification renforcee EST controlee ici, contrairement a
    l appartenance. La raison tient a ce que chaque controle revele : le niveau
    exige est une propriete de la POLITIQUE, publique par nature, et ne dit rien
    d une ressource. Ne pas la controler ici laisserait passer sans preuve
    d identite fraiche toute action renforcee dont la vue ne charge aucun objet
    — `ORGANIZER_APPROVE` en est une. Le trou serait invisible : le controle
    existerait dans le moteur mais ne serait jamais atteint.

    ATTENTION : une reponse favorable N AUTORISE RIEN sur une instance
    particuliere. Elle doit toujours etre suivie soit d un `authorize()` avec la
    ressource — via `has_object_permission` — soit d un filtrage de la requete
    SQL par les gestionnaires de S1-A.1b (`Session.objects.for_user`,
    `Device.objects.for_user`). Une vue de liste qui se contenterait de
    `may_attempt` exposerait les donnees de tous les utilisateurs. Le nom de la
    fonction est choisi pour que cette faiblesse soit lisible sur l appel.
    """
    if not subject.is_authenticated:
        return deny(Reason.UNAUTHENTICATED)
    if not subject.is_active:
        return deny(Reason.INACTIVE_SUBJECT)

    grants = POLICY.get(subject.role or "")
    if grants is None:
        return deny(Reason.UNKNOWN_ROLE)
    if not isinstance(action, Action):
        return deny(Reason.UNKNOWN_ACTION)

    grant = grants.get(action)
    if grant is None:
        return deny(Reason.ROLE_NOT_GRANTED)
    if grant.step_up and subject.auth_level < AUTH_LEVEL_STEP_UP:
        return deny(Reason.STEP_UP_REQUIRED)
    return ALLOW
