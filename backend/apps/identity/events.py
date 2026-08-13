"""
Evenements emis par le contexte `identity`.

Un evenement est un CONTRAT PUBLIC : d autres contextes s y abonneront et le
paiement d une rupture se fait chez eux, pas ici. D ou trois regles appliquees
dans ce module.

**Le type est versionne et fige.** `identity.user.registered` v1 ne change
jamais de forme ; un besoin nouveau produit une v2, jamais une v1 modifiee.

**La charge utile est minimale.** Elle ne porte PAS l adresse electronique.
Un consommateur qui doit envoyer un courriel de bienvenue resout lui-meme
`user_id -> email` au moment de l envoi. Deux raisons, et la seconde est la plus
importante :

- l `outbox` est conservee 30 jours (`OUTBOX_RETENTION_DAYS`) et relayee vers un
  courtier : y recopier une donnee personnelle la duplique hors du perimetre ou
  l anonymisation RGPD (Sprint 5) sait aller la chercher ;
- une charge utile qui porte l etat complet invite les consommateurs a le traiter
  comme la verite, alors qu il est deja perime a la lecture.

**Aucun secret, jamais.** Ni mot de passe, ni empreinte, ni jeton — meme hache.
Un test le verifie sur la charge reelle plutot que sur l intention.
"""

from __future__ import annotations

from typing import Any, Final

#: `<contexte>.<agregat>.<fait accompli au passe>` — un evenement decrit ce qui
#: A EU LIEU. Nommer un evenement a l imperatif (`send_welcome_email`) en ferait
#: une commande deguisee, et coupler l emetteur aux reactions attendues.
USER_REGISTERED: Final = "identity.user.registered"

AGGREGATE_USER: Final = "user"


def user_registered_payload(*, role_name: str) -> dict[str, Any]:
    """
    Charge utile de `identity.user.registered` v1.

    L identifiant de l utilisateur n y figure pas : il est deja porte par
    `aggregate_id`, et le dupliquer creerait deux endroits ou une incoherence
    peut apparaitre.
    """
    return {"role": role_name}
