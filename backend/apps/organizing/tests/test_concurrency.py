from __future__ import annotations

import datetime
import threading

import pytest
from django.contrib.auth import get_user_model
from django.db import connections
from django.utils import timezone

from apps.core.exceptions import StaleResourceError
from apps.core.outbox.models import OutboxEvent
from apps.organizing.constants import ORGANIZER_APPROVED
from apps.organizing.events import ORGANIZER_APPROVED_EVENT
from apps.organizing.models import Organizer
from apps.organizing.services import OrganizerOnboardingService

User = get_user_model()

PASSWORD = "Chataigne-Orageuse-2026"


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_approvals_have_exactly_one_winner(roles):
    """
    Exigence S1 §6.3.

    Deux administrateurs partent de la meme version du meme dossier.
    La base doit arbitrer l UPDATE conditionnel :

    - exactement une approbation reussit ;
    - exactement une requete recoit STALE_RESOURCE ;
    - la version n est incrementee qu une fois ;
    - un seul evenement Outbox est emis.
    """
    applicant = User.objects.create_user(
        email="candidate-concurrency@example.test",
        password=PASSWORD,
        first_name="Nora",
        last_name="Amari",
        date_of_birth=datetime.date(1992, 4, 7),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )
    admin_one = User.objects.create_user(
        email="admin-one-concurrency@example.test",
        password=PASSWORD,
        first_name="Admin",
        last_name="One",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["ADMIN"],
    )
    admin_two = User.objects.create_user(
        email="admin-two-concurrency@example.test",
        password=PASSWORD,
        first_name="Admin",
        last_name="Two",
        date_of_birth=datetime.date(1990, 1, 2),
        terms_accepted_at=timezone.now(),
        role=roles["ADMIN"],
    )

    organizer = Organizer.objects.create(
        user=applicant,
        org_name="Concurrency Arena",
        contact_email="contact-concurrency@example.test",
    )

    initial_version = organizer.version
    barrier = threading.Barrier(2)
    results: list[tuple[str, object]] = []
    results_lock = threading.Lock()

    def worker(actor_id) -> None:
        connections.close_all()

        try:
            barrier.wait()

            result = OrganizerOnboardingService.approve(
                organizer_id=organizer.pk,
                actor_id=actor_id,
                expected_version=initial_version,
            )

            outcome: tuple[str, object] = ("success", result.version)

        except StaleResourceError as exc:
            outcome = ("stale", exc.details)

        finally:
            connections.close_all()

        with results_lock:
            results.append(outcome)

    threads = [
        threading.Thread(target=worker, args=(admin_one.pk,)),
        threading.Thread(target=worker, args=(admin_two.pk,)),
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    organizer.refresh_from_db()

    successes = [value for kind, value in results if kind == "success"]
    stale = [value for kind, value in results if kind == "stale"]

    assert len(results) == 2, results
    assert successes == [initial_version + 1], results
    assert stale == [{"current_version": initial_version + 1}], results

    assert organizer.validation_status == ORGANIZER_APPROVED
    assert organizer.version == initial_version + 1
    assert organizer.validated_by_id in {admin_one.pk, admin_two.pk}

    events = OutboxEvent.objects.filter(
        aggregate_id=organizer.pk,
        event_type=ORGANIZER_APPROVED_EVENT,
    )

    assert events.count() == 1
    assert events.get().actor_id == organizer.validated_by_id
