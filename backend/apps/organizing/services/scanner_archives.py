from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import ConflictError, NotFoundBusinessError, StaleResourceError

from ..constants import SCANNER_DELETED, SCANNER_INVITATION_CANCELLED
from ..models import Organizer, Scanner


class ScannerArchiveService:
    ARCHIVABLE_STATUSES = {
        SCANNER_INVITATION_CANCELLED,
        SCANNER_DELETED,
    }

    @staticmethod
    def archive_many(
        *,
        organizer: Organizer,
        actor_id: Any,
        items: list[dict[str, Any]],
    ) -> int:
        archived = 0

        with transaction.atomic():
            for item in items:
                scanner = (
                    Scanner.objects.select_for_update()
                    .filter(
                        pk=item["id"],
                        organizer=organizer,
                        archived_at__isnull=True,
                    )
                    .first()
                )

                if scanner is None:
                    raise NotFoundBusinessError()

                expected_version = item["version"]

                if scanner.version != expected_version:
                    raise StaleResourceError(
                        details={
                            "scanner_id": str(scanner.pk),
                            "current_version": scanner.version,
                        },
                    )

                if scanner.status not in ScannerArchiveService.ARCHIVABLE_STATUSES:
                    raise ConflictError(
                        code="SCANNER_NOT_ARCHIVABLE",
                        message=(
                            "Seuls les anciens scanners déjà annulés "
                            "ou retirés peuvent être supprimés de la liste."
                        ),
                    )

                scanner.archived_at = timezone.now()
                scanner.archived_by_id = actor_id
                scanner.version += 1

                scanner.save(
                    update_fields=[
                        "archived_at",
                        "archived_by",
                        "version",
                        "updated_at",
                    ],
                )

                archived += 1

        return archived
