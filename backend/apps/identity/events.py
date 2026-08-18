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


#: Emis a chaque ouverture de session reussie. Consomme au Sprint 4 par
#: `notifying` pour l alerte « nouvelle connexion ».
USER_LOGGED_IN: Final = "identity.user.logged_in"


def user_logged_in_payload(*, role_name: str, device_bound: bool) -> dict[str, Any]:
    """
    Charge utile de `identity.user.logged_in` v1.

    Ni adresse IP, ni `User-Agent`, ni empreinte. Ces elements existent sur la
    ligne `session` — a laquelle `aggregate_id` donne acces — et les recopier
    dans une `outbox` conservee 30 jours et relayee vers un courtier les
    dupliquerait hors du perimetre que l anonymisation RGPD sait atteindre.

    `device_bound` suffit au consommateur : une connexion depuis un appareil
    nouvellement lie merite une notification, les autres non.
    """
    return {"role": role_name, "device_bound": device_bound}


#: Emis quand un code de reinitialisation est REELLEMENT cree. Le chemin
#: anti-enumeration — identifiants faux, adresse inconnue — n emet rien : un
#: evenement par tentative transformerait l `outbox` en journal des adresses
#: essayees, ce que la charge utile s interdit par ailleurs.
DEVICE_RESET_REQUESTED: Final = "identity.device.reset.requested"


def device_reset_requested_payload(*, device_bound: bool) -> dict[str, Any]:
    """
    Charge utile de `identity.device.reset.requested` v1.

    Ni adresse, ni code, ni empreinte, ni identifiant de defi. `device_bound`
    suffit au consommateur : une demande de reinitialisation sur un compte qui
    n a aucun appareil lie n a pas le meme sens qu une demande sur un compte
    verrouille, et c est la seule nuance qu une alerte a besoin de connaitre.
    """
    return {"device_bound": device_bound}


#: Emis quand le code a ete verifie et l appareil delie.
DEVICE_RESET_CONFIRMED: Final = "identity.device.reset.confirmed"


def device_reset_confirmed_payload(*, device_revoked: bool, sessions_revoked: int) -> dict[str, Any]:
    """
    Charge utile de `identity.device.reset.confirmed` v1.

    Le nombre de sessions fermees est une donnee d audit utile — une
    reinitialisation qui en ferme huit merite un regard — et ne designe
    personne. L identifiant de l appareil n y figure pas : il est deja perime a
    la lecture, puisque la ligne est revoquee.
    """
    return {"device_revoked": device_revoked, "sessions_revoked": sessions_revoked}
