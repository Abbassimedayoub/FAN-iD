"""
Le resultat d une decision d autorisation.

Deux exigences opposees se rencontrent ici :

- l EXPLOITATION a besoin de savoir POURQUOI un acces a ete refuse, sinon un
  refus legitime et un bug de configuration se ressemblent dans les journaux ;
- le CLIENT ne doit rien apprendre de plus que « non ». Distinguer « tu n as pas
  le role » de « ce n est pas ta ressource » transforme l API en oracle
  d existence : un attaquant enumere les identifiants en lisant les codes
  d erreur, sans jamais obtenir une seule donnee.

D ou la separation : `Reason` est un code interne, destine aux journaux et aux
metriques ; il n est jamais renvoye tel quel au client. L adaptateur DRF
(`permissions.py`) traduit les refus en `FORBIDDEN` opaque, sauf lorsqu une
action client explicite est possible : `STEP_UP_REQUIRED` pour fournir une
preuve renforcee, et `ORGANIZER_NOT_APPROVED` pour attendre ou obtenir la
validation du dossier. Aucun de ces codes ne revele l existence d une ressource.

Les valeurs de `Reason` sont volontairement en nombre fini et sans donnee
variable : elles servent d etiquette Prometheus. Une etiquette portant un
identifiant de ressource ou un message d erreur ferait exploser la cardinalite
et exfiltrerait des donnees personnelles dans la supervision (regle §Metriques).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Reason(StrEnum):
    """Motif stable d une decision. Cardinalite bornee, aucune donnee variable."""

    ALLOWED = "allowed"
    #: Aucun sujet authentifie.
    UNAUTHENTICATED = "unauthenticated"
    #: Compte desactive ou anonymise (RGPD) : plus aucun droit, meme sur soi.
    INACTIVE_SUBJECT = "inactive_subject"
    #: Role inconnu du referentiel — donnee corrompue ou role retire du code.
    UNKNOWN_ROLE = "unknown_role"
    #: Action absente du catalogue — faute de frappe ou action non declaree.
    UNKNOWN_ACTION = "unknown_action"
    #: Le role existe mais cette action ne lui est pas accordee.
    ROLE_NOT_GRANTED = "role_not_granted"
    #: Le role est accorde mais la ressource n appartient pas au sujet.
    NOT_OWNER = "not_owner"
    #: La ressource ne porte pas l attribut exige par la regle.
    RESOURCE_ATTRIBUTE_MISSING = "resource_attribute_missing"
    #: L organisateur existe mais n a pas encore ete approuve.
    ORGANIZER_NOT_APPROVED = "organizer_not_approved"
    #: Droits suffisants, mais verification renforcee exigee et non fournie.
    STEP_UP_REQUIRED = "step_up_required"


@dataclass(frozen=True, slots=True)
class Decision:
    """
    Verdict du moteur.

    `bool(decision)` LEVE une exception. Par defaut, une dataclass est toujours
    vraie : `if decision:` autoriserait donc tous les refus, sans bruit, sans
    trace, et en passant la revue de code. Plutot que de documenter ce piege en
    esperant qu on le lise, on le rend impossible — la faute devient une panne
    immediate et lisible au lieu d une faille silencieuse.
    """

    allowed: bool
    reason: Reason

    def __bool__(self) -> bool:
        raise TypeError(
            "Une Decision ne se teste pas par sa verite : ecrire `decision.allowed`. "
            "`if decision:` serait toujours vrai et autoriserait tous les refus."
        )

    def __post_init__(self) -> None:
        # Garde-fou contre une construction incoherente : un `Decision(True,
        # Reason.NOT_OWNER)` passerait tous les tests de bord et ruinerait
        # l exploitabilite des journaux.
        coherent = self.allowed is (self.reason is Reason.ALLOWED)
        if not coherent:
            raise ValueError(f"decision incoherente : allowed={self.allowed} reason={self.reason}")


#: Instance unique du verdict positif : une decision favorable n a qu une forme.
ALLOW = Decision(allowed=True, reason=Reason.ALLOWED)


def deny(reason: Reason) -> Decision:
    """Construit un refus. Interdit de refuser avec le motif `ALLOWED`."""
    if reason is Reason.ALLOWED:
        raise ValueError("un refus ne peut pas porter le motif ALLOWED")
    return Decision(allowed=False, reason=reason)
