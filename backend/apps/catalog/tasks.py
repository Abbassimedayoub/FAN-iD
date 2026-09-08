from __future__ import annotations

from celery import shared_task

from .services.completion import complete_elapsed_events


@shared_task(
    name="catalog.complete_elapsed_events",
    ignore_result=True,
)
def complete_elapsed_events_task() -> dict[str, int]:
    return {
        "completed": complete_elapsed_events(),
    }
