"""
Adaptateurs DRF. Ils ADAPTENT, ils ne decident pas.

Chacune des classes ci-dessous se contente de repondre a deux questions —
« quelle action la vue tente-t-elle ? » et « quelle ressource vise-t-elle ? » —
puis delegue le verdict au moteur. Aucune ne compare un role, aucune ne teste
`is_staff`. C est ce qui permet d affirmer que la matrice de `rules.py` decrit
REELLEMENT le comportement du systeme : il n existe pas de second endroit ou
une autorisation se joue.

Elles se distinguent uniquement par la STRATEGIE DE RESOLUTION de l action et de
la ressource :

| Classe                          | Action                        | Ressource                |
|---------------------------------|-------------------------------|--------------------------|
| `BasePolicyPermission`          | `required_action` de la vue   | aucune                   |
| `ActionPermission`              | + table `policy_actions`      | aucune                   |
| `SelfResourcePermission`        | idem                          | `obj.user_id`            |
| `OrganizerResourcePermission`   | idem                          | `obj.organizer_id`       |
| `MethodScopedActionPermission`  | lecture / ecriture selon HTTP | heritee                  |

`DenyAll`, le refus par defaut du projet, vit dans `apps.core.permissions` : il
ne consulte aucune politique, c est un garde-fou de cadriciel et non une regle
metier, et `core` peut servir de defaut a tout le projet sans dependre d un
contexte borne (ADR-S-01).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, ClassVar

from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.core.observability.metrics import AUTHZ_ROLE_ANONYMOUS, fanid_authz_denied_total

from .authz import Action, Decision, Reason, Resource, authorize, may_attempt
from .authz.context import subject_from_request

logger = logging.getLogger(__name__)

#: Message unique renvoye au client pour TOUT refus, quel qu en soit le motif.
#:
#: Distinguer « role insuffisant » de « ressource d autrui » transformerait
#: l API en oracle : en lisant le code d erreur, un attaquant apprendrait quels
#: identifiants existent, sans jamais obtenir une seule donnee. Le motif precis
#: part dans les journaux, correle par `correlation_id`.
FORBIDDEN_MESSAGE = "Vous n avez pas la permission d effectuer cette action."
FORBIDDEN_CODE = "FORBIDDEN"

#: Seule exception a l opacite : le client DOIT savoir qu une verification
#: renforcee est attendue, sinon il ne peut rien entreprendre. Ce code ne revele
#: rien sur la ressource — il n est renvoye qu a un sujet dont l appartenance a
#: DEJA ete verifiee (cf. l ordre des controles dans `engine.authorize`).
STEP_UP_MESSAGE = "Une verification d identite renforcee est requise pour cette action."
STEP_UP_CODE = "STEP_UP_REQUIRED"


class BasePolicyPermission(BasePermission):
    """
    Socle commun : resout l action, delegue, traduit le refus.

    Par defaut, aucune ressource n est associee. Une action de portee `SELF` ou
    `OWN_ORGANIZER` verifiee par cette classe seule sera donc REFUSEE
    (`RESOURCE_ATTRIBUTE_MISSING`) : le socle ne peut pas ouvrir un acces par
    omission, il faut choisir explicitement une sous-classe qui sait designer la
    ressource.
    """

    #: Action portee par la vue quand elle n en a qu une.
    required_action: ClassVar[Action | None] = None

    #: Lus par DRF pour construire la reponse 403. Declares ici parce que
    #: `BasePermission` ne les definit pas : sans cela, l affectation dans
    #: `_resolve` serait un attribut cree a la volee, invisible pour mypy.
    message: str = FORBIDDEN_MESSAGE
    code: str = FORBIDDEN_CODE

    def get_action(self, request: Any, view: Any) -> Action | None:
        action = getattr(view, "required_action", None) or self.required_action
        return action if isinstance(action, Action) else None

    def get_resource(self, request: Any, view: Any, obj: Any) -> Resource:
        return Resource()

    # -- points d entree DRF ------------------------------------------------

    def has_permission(self, request: Any, view: Any) -> bool:
        """
        Pre-controle appele AVANT le chargement de l objet.

        Il ne verifie donc que le volet RBAC. Une vue de detail est ensuite
        repassee par `has_object_permission` ; une vue de LISTE, elle, ne l est
        jamais — c est a son `get_queryset()` de filtrer, via les gestionnaires
        du lot S1-A.1b (`Device.objects.for_user`, `Session.objects.for_user`).
        Cette limite est structurelle a DRF, pas a ce code : la nommer ici evite
        qu on la decouvre en production.
        """
        action = self.get_action(request, view)
        if action is None:
            return self._deny_misconfigured(view)

        subject = subject_from_request(request)
        return self._resolve(
            may_attempt(subject, action),
            action,
            role=subject.role,
        )

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        action = self.get_action(request, view)
        if action is None:
            return self._deny_misconfigured(view)

        subject = subject_from_request(request)
        decision = authorize(
            subject,
            action,
            self.get_resource(request, view, obj),
        )
        return self._resolve(
            decision,
            action,
            role=subject.role,
        )

    # -- traduction ---------------------------------------------------------

    def _resolve(
        self,
        decision: Decision,
        action: Action,
        *,
        role: str | None,
    ) -> bool:
        if decision.allowed:
            return True

        step_up = decision.reason is Reason.STEP_UP_REQUIRED
        # DRF lit `self.message` et `self.code` sur l INSTANCE de permission
        # pour construire la reponse 403. Les permissions sont instanciees a
        # chaque requete par `APIView.get_permissions()`, il n y a donc pas de
        # fuite d etat entre requetes concurrentes.
        self.message = STEP_UP_MESSAGE if step_up else FORBIDDEN_MESSAGE
        self.code = STEP_UP_CODE if step_up else FORBIDDEN_CODE

        # Journal : action, motif et role suffisent au diagnostic. Ni
        # identifiant d utilisateur ni identifiant de ressource — le
        # `correlation_id` deja pose par le middleware relie cette ligne a la
        # requete, qui porte le reste. Ces trois champs sont de cardinalite
        # bornee, donc reutilisables tels quels comme etiquettes de metrique au
        # lot S1-A.9.
        metric_role = role if role is not None else AUTHZ_ROLE_ANONYMOUS

        fanid_authz_denied_total.labels(
            action=str(action),
            role=metric_role,
        ).inc()

        logger.warning(
            "authorization.denied",
            extra={
                "authz_action": str(action),
                "authz_reason": decision.reason.value,
                "authz_role": metric_role,
            },
        )
        return False

    def _deny_misconfigured(self, view: Any) -> bool:
        """
        Vue sans action declaree : refus, et journal de niveau ERREUR.

        C est un defaut de configuration, pas un refus metier. Le distinguer
        evite de chercher une regle d autorisation la ou il manque une ligne
        `required_action` — et evite surtout la tentation inverse, qui serait
        d autoriser « puisqu aucune regle ne s applique ».
        """
        self.message = FORBIDDEN_MESSAGE
        self.code = FORBIDDEN_CODE
        logger.error(
            "authorization.misconfigured_view",
            extra={"authz_view": type(view).__name__},
        )
        return False


class ActionPermission(BasePolicyPermission):
    """
    Resout l action depuis la table `policy_actions` du `ViewSet`.

        class DeviceViewSet(ModelViewSet):
            policy_actions = {
                "list": Action.DEVICE_LIST_SELF,
                "revoke": Action.DEVICE_REVOKE_SELF,
            }
            permission_classes = [SelfResourcePermission]

    Une entree manquante n est PAS une autorisation implicite : la resolution
    echoue et la requete est refusee. Ajouter une methode a un `ViewSet` sans
    lui donner d action la rend donc inaccessible, ce qui est le sens voulu du
    « deny by default » — la panne est visible en developpement, la faille ne
    l aurait pas ete.
    """

    def get_action(self, request: Any, view: Any) -> Action | None:
        table: Mapping[str, Action] = getattr(view, "policy_actions", {}) or {}
        viewset_action = getattr(view, "action", None)
        if viewset_action is not None and viewset_action in table:
            candidate = table[viewset_action]
            return candidate if isinstance(candidate, Action) else None
        return super().get_action(request, view)


class SelfResourcePermission(ActionPermission):
    """
    Ressource appartenant au sujet, designee par une colonne de rattachement.

    `owner_lookup` vaut `user_id` par defaut, ce qui couvre `Device`, `Session`
    et `MfaChallenge`. Pour un point de terminaison dont l objet EST
    l utilisateur, declarer `owner_lookup = "pk"` dans la sous-classe. Cette
    designation est explicite plutot que devinee : deduire le proprietaire du
    type de l objet marcherait jusqu au jour ou un modele nommerait sa colonne
    autrement, et ce jour-la le controle passerait sans rien verifier.
    """

    owner_lookup: ClassVar[str] = "user_id"

    def get_resource(self, request: Any, view: Any, obj: Any) -> Resource:
        return Resource(owner_id=getattr(obj, self.owner_lookup, None))


class OrganizerResourcePermission(ActionPermission):
    """Ressource rattachee a un organisateur (`obj.organizer_id`)."""

    organizer_lookup: ClassVar[str] = "organizer_id"

    def get_resource(self, request: Any, view: Any, obj: Any) -> Resource:
        return Resource(organizer_id=getattr(obj, self.organizer_lookup, None))


class MethodScopedActionPermission(SelfResourcePermission):
    """
    Deux actions pour un meme point de terminaison, selon la methode HTTP.

        class MeView(RetrieveUpdateAPIView):
            read_action = Action.USER_READ_SELF
            write_action = Action.USER_UPDATE_SELF

    `GET`, `HEAD` et `OPTIONS` passent par l action de lecture ; tout le reste
    par celle d ecriture. `OPTIONS` est traite comme une lecture parce que DRF
    y expose le schema du point de terminaison : ce n est pas anodin, mais c est
    strictement moins que ce que `GET` renvoie.
    """

    read_action: ClassVar[Action | None] = None
    write_action: ClassVar[Action | None] = None

    def get_action(self, request: Any, view: Any) -> Action | None:
        safe = request.method in SAFE_METHODS
        attribute = "read_action" if safe else "write_action"
        action = getattr(view, attribute, None) or getattr(self, attribute, None)
        return action if isinstance(action, Action) else None
