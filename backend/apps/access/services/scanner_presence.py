from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import PermissionBusinessError
from apps.organizing.constants import SCANNER_ACTIVE
from apps.organizing.models import Scanner

from ..models import ScannerPresence


class ScannerInactiveError(PermissionBusinessError):
    default_code = "SCANNER_INACTIVE"
    default_message = "Ce compte scanner n'est pas actif."


@transaction.atomic
def record_scanner_heartbeat(*, scanner_user_id: UUID) -> ScannerPresence:
    scanner = (
        Scanner.objects.select_for_update()
        .filter(
            user_id=scanner_user_id,
            status=SCANNER_ACTIVE,
        )
        .first()
    )
    if scanner is None:
        raise ScannerInactiveError()

    presence, _ = ScannerPresence.objects.update_or_create(
        scanner=scanner,
        defaults={"last_seen_at": timezone.now()},
    )
    return presence
