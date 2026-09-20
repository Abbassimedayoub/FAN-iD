"""
Closed catalog of actions subject to authorization.

An action is a business verb rather than a route or HTTP method. Keeping actions
in a StrEnum gives type checking, stable string values for logs/metrics, and an
iterable catalog that exhaustive policy tests can cover.

Naming convention: `<context>:<resource>:<verb>`.
"""

from enum import StrEnum


class Action(StrEnum):
    """Catalog of business actions subject to authorization."""

    # --- Personal account ------------------------------------------------
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
