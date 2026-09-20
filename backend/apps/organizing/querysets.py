"""
QuerySets for the `organizing` context.

A scope filter written inside a single view protects only that view. Defining
it here makes the rule reusable and keeps "who can see what" readable in one
place.
"""

from __future__ import annotations

from typing import Any

from django.db import models

from .constants import ORGANIZER_APPROVED, ORGANIZER_PENDING


class OrganizerQuerySet(models.QuerySet):
    """Business-named scope filters rather than column-named helpers."""

    def approved(self) -> "OrganizerQuerySet":
        """Return only approved organizers."""
        return self.filter(validation_status=ORGANIZER_APPROVED)

    def pending(self) -> "OrganizerQuerySet":
        """Return the administration review queue."""
        return self.filter(validation_status=ORGANIZER_PENDING)

    def with_user(self) -> "OrganizerQuerySet":
        """
        Load the linked account in the same query.

        Administration lists display the applicant email; without this helper a
        page of twenty rows would trigger twenty-one queries.
        """
        return self.select_related("user")

    def for_user(self, user: Any) -> "OrganizerQuerySet":
        return self.filter(user=user)
