import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizing.constants import ORGANIZER_SUSPENDED
from apps.organizing.models import Organizer, OrganizerReactivationRequest


PASSWORD = "StrongPass123!"


def make_user(*, roles, role_name: str, index: int):
    User = get_user_model()

    return User.objects.create_user(
        email=f"admin-reactivation-home-{role_name.lower()}-{index}@example.test",
        password=PASSWORD,
        first_name="Test",
        last_name=f"{role_name}-{index}",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles[role_name],
    )


@pytest.mark.django_db
def test_admin_list_exposes_pending_reactivation_notifications(roles):
    admin = make_user(
        roles=roles,
        role_name="ADMIN",
        index=1,
    )

    organizer_ids = set()

    for index in range(6):
        owner = make_user(
            roles=roles,
            role_name="ORGANIZER",
            index=index,
        )

        organizer = Organizer.objects.create(
            user=owner,
            org_name=f"Reactivation Home {index}",
            contact_email=f"reactivation-home-{index}@example.test",
            validation_status=ORGANIZER_SUSPENDED,
        )

        OrganizerReactivationRequest.objects.create(
            organizer=organizer,
            requested_by=owner,
            organizer_version=organizer.version,
        )

        organizer_ids.add(str(organizer.pk))

    client = APIClient()
    client.force_authenticate(user=admin)

    response = client.get("/api/v1/admin/organizers/")

    assert response.status_code == 200, response.data
    assert response.data["pending_reactivation_count"] == 6
    assert len(response.data["pending_reactivations"]) == 5

    returned_organizer_ids = {
        item["organizer_id"]
        for item in response.data["pending_reactivations"]
    }

    assert returned_organizer_ids <= organizer_ids

    for item in response.data["pending_reactivations"]:
        assert item["id"]
        assert item["organizer_id"]
        assert item["organizer_name"].startswith("Reactivation Home ")
        assert item["created_at"]


@pytest.mark.django_db
def test_admin_list_has_empty_reactivation_notifications_without_pending_request(
    roles,
):
    admin = make_user(
        roles=roles,
        role_name="ADMIN",
        index=99,
    )

    client = APIClient()
    client.force_authenticate(user=admin)

    response = client.get("/api/v1/admin/organizers/")

    assert response.status_code == 200, response.data
    assert response.data["pending_reactivation_count"] == 0
    assert response.data["pending_reactivations"] == []
