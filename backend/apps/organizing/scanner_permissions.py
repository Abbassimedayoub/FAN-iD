from apps.identity.api import (
    Action,
    MethodScopedActionPermission,
)


class OrganizerScannerCollectionPermission(MethodScopedActionPermission):
    read_action = Action.SCANNER_READ
    write_action = Action.SCANNER_INVITE


class OrganizerScannerResourcePermission(MethodScopedActionPermission):
    read_action = Action.SCANNER_READ
    write_action = Action.SCANNER_REVOKE


class OrganizerScannerCredentialPermission(MethodScopedActionPermission):
    read_action = Action.SCANNER_READ
    write_action = Action.SCANNER_CREDENTIAL_RESET
