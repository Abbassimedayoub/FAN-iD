"""
Catalogue ferme des actions soumises a autorisation.

Une action est un VERBE METIER, pas une route ni une methode HTTP. Deux routes
peuvent porter la meme action ; une meme route peut porter deux actions selon la
methode. Nommer l action d apres la route reviendrait a autoriser l URL plutot
que l intention — et rendrait impossible de repondre a la question qui compte
reellement lors d un audit : « qui peut revoquer un appareil ? ».

`StrEnum` plutot qu un module de constantes :

- mypy refuse une action inexistante au moment du type-check, la ou une chaine
  libre ne se trahirait qu en production, sous la forme d un `DENIED_UNKNOWN_ACTION`
  silencieux ;
- la valeur reste une `str` a l execution, donc utilisable telle quelle comme
  etiquette Prometheus et comme champ de journal ;
- l enumeration est iterable, ce qui permet a la matrice de test de prouver
  qu AUCUNE action n a ete oubliee. Ajouter un membre ici fait echouer le test
  tant que la politique n a pas ete decidee explicitement. C est voulu : une
  action sans decision est une faille en attente.

Convention de nommage : `<contexte>:<ressource>:<verbe>`. Le prefixe de contexte
n autorise aucun import croise — il documente a qui appartient la regle.
"""

from enum import StrEnum


class Action(StrEnum):
    """Catalogue des actions métier soumises à autorisation."""

    # --- Compte personnel -----------------------------------------------
    USER_READ_SELF = "identity:user:read_self"
    USER_UPDATE_SELF = "identity:user:update_self"
    USER_DELETE_SELF = "identity:user:delete_self"

    # --- Appareils et sessions ------------------------------------------
    DEVICE_LIST_SELF = "identity:device:list_self"
    DEVICE_REVOKE_SELF = "identity:device:revoke_self"
    SESSION_LIST_SELF = "identity:session:list_self"
    SESSION_REVOKE_SELF = "identity:session:revoke_self"

    # --- Organisateur ----------------------------------------------------
    ORGANIZER_CREATE = "organizing:organizer:create"
    ORGANIZER_READ = "organizing:organizer:read"
    ORGANIZER_UPDATE = "organizing:organizer:update"
    ORGANIZER_APPROVE = "organizing:organizer:approve"
    ORGANIZER_REJECT = "organizing:organizer:reject"
    ORGANIZER_SUSPEND = "organizing:organizer:suspend"

    # --- Scanners organisateur -------------------------------------------
    SCANNER_INVITE = "organizing:scanner:invite"
    SCANNER_READ = "organizing:scanner:read"
    SCANNER_REVOKE = "organizing:scanner:revoke"
    SCANNER_CREDENTIAL_RESET = "organizing:scanner:credential-reset"

    # --- Catalogue --------------------------------------------------------
    CATEGORY_READ = "catalog:category:read"
    CATEGORY_CREATE = "catalog:category:create"
    CATEGORY_DELETE = "catalog:category:delete"
    EVENT_CREATE = "catalog:event:create"
    EVENT_READ = "catalog:event:read"
    EVENT_UPDATE = "catalog:event:update"
    EVENT_DELETE = "catalog:event:delete"
    EVENT_PUBLISH = "catalog:event:publish"
    EVENT_ARCHIVE = "catalog:event:archive"
    EVENT_UNARCHIVE = "catalog:event:unarchive"
    EVENT_POSTPONE = "catalog:event:postpone"
    EVENT_SUSPEND = "catalog:event:suspend"
    EVENT_CANCEL = "catalog:event:cancel"

    TICKET_CATEGORY_CREATE = "catalog:ticket-category:create"
    TICKET_CATEGORY_READ = "catalog:ticket-category:read"
    TICKET_CATEGORY_UPDATE = "catalog:ticket-category:update"
    TICKET_CATEGORY_DELETE = "catalog:ticket-category:delete"

    # --- Controle d acces -------------------------------------------------
    TICKET_SCAN = "access:ticket:scan"
