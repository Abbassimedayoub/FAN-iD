from __future__ import annotations

import datetime
import io

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Category, Event
from apps.core.adapters.storage import InMemoryStorage, LocalStorage

User = get_user_model()

APPROVED = "APPROVED"

PNG = b"\x89PNG\r\n\x1a\n" + b"fanid-event-image"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(
        name="Image Event",
    )


@pytest.fixture
def storage(
    monkeypatch,
) -> InMemoryStorage:
    value = InMemoryStorage()

    monkeypatch.setattr(
        "apps.catalog.views." "build_object_storage",
        lambda: value,
    )

    monkeypatch.setattr(
        "apps.catalog.serializers." "build_object_storage",
        lambda: value,
    )

    return value


def make_organizer(
    roles,
    *,
    suffix: str,
):
    user = User.objects.create_user(
        email=(f"image-{suffix}" "@example.test"),
        password="Chataigne-Orageuse-2026",
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(
            1990,
            3,
            12,
        ),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )

    Organizer = apps.get_model(
        "organizing",
        "Organizer",
    )

    organizer = Organizer.objects.create(
        user=user,
        org_name=f"Organisation {suffix}",
        contact_email=(f"contact-{suffix}" "@example.test"),
        validation_status=APPROVED,
        commission_agreed_at=timezone.now(),
    )

    return user, organizer


def make_event(
    *,
    organizer,
    category,
    suffix: str,
) -> Event:
    start = timezone.now() + datetime.timedelta(days=10)

    return Event.objects.create(
        organizer=organizer,
        category=category,
        name=f"Image Event {suffix}",
        description="Image phase 2C",
        starts_at=start,
        ends_at=(start + datetime.timedelta(hours=2)),
        venue="Stade FANID",
        capacity_total=1000,
    )


def auth(
    client: APIClient,
    user,
) -> APIClient:
    client.force_authenticate(user=user)
    return client


def image_file(
    *,
    content: bytes = PNG,
    content_type: str = "image/png",
):
    return SimpleUploadedFile(
        "poster.png",
        content,
        content_type=content_type,
    )


@pytest.mark.django_db
def test_owner_can_upload_event_image(
    client,
    category,
    roles,
    storage,
):
    user, organizer = make_organizer(
        roles,
        suffix="upload",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="upload",
    )

    response = auth(
        client,
        user,
    ).put(
        f"/api/v1/events/{event.pk}/image",
        {
            "image": image_file(),
        },
        format="multipart",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 200
    assert response["ETag"] == '"2"'
    assert response.data["version"] == 2

    assert response.data["image_url"].startswith("memory://events/")

    event.refresh_from_db()

    assert event.image_key.endswith(".png")
    assert event.image_key in (storage._objects)


@pytest.mark.django_db
def test_upload_requires_if_match_before_storage_write(
    client,
    category,
    roles,
    storage,
):
    user, organizer = make_organizer(
        roles,
        suffix="missing-match",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="missing-match",
    )

    response = auth(
        client,
        user,
    ).put(
        f"/api/v1/events/{event.pk}/image",
        {
            "image": image_file(),
        },
        format="multipart",
    )

    assert response.status_code == 428
    assert storage._objects == {}


@pytest.mark.django_db
def test_upload_rejects_non_image_content(
    client,
    category,
    roles,
    storage,
):
    user, organizer = make_organizer(
        roles,
        suffix="bad-content",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="bad-content",
    )

    response = auth(
        client,
        user,
    ).put(
        f"/api/v1/events/{event.pk}/image",
        {
            "image": image_file(
                content=b"not-a-png",
            ),
        },
        format="multipart",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 400
    assert storage._objects == {}


@pytest.mark.django_db
def test_upload_rejects_more_than_five_megabytes(
    client,
    category,
    roles,
    storage,
):
    user, organizer = make_organizer(
        roles,
        suffix="too-large",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="too-large",
    )

    content = b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024)

    response = auth(
        client,
        user,
    ).put(
        f"/api/v1/events/{event.pk}/image",
        {
            "image": image_file(
                content=content,
            ),
        },
        format="multipart",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 400
    assert storage._objects == {}


@pytest.mark.django_db
def test_foreign_event_image_is_hidden(
    client,
    category,
    roles,
    storage,
):
    user, _ = make_organizer(
        roles,
        suffix="reader",
    )

    _, foreign = make_organizer(
        roles,
        suffix="foreign",
    )

    event = make_event(
        organizer=foreign,
        category=category,
        suffix="foreign",
    )

    response = auth(
        client,
        user,
    ).put(
        f"/api/v1/events/{event.pk}/image",
        {
            "image": image_file(),
        },
        format="multipart",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 404
    assert storage._objects == {}


@pytest.mark.django_db
def test_published_event_image_cannot_change(
    client,
    category,
    roles,
    storage,
):
    user, organizer = make_organizer(
        roles,
        suffix="published",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="published",
    )

    event.status = Event.PUBLISHED
    event.published_at = timezone.now()

    event.save(
        update_fields=[
            "status",
            "published_at",
        ]
    )

    response = auth(
        client,
        user,
    ).put(
        f"/api/v1/events/{event.pk}/image",
        {
            "image": image_file(),
        },
        format="multipart",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409
    assert storage._objects == {}


@pytest.mark.django_db
def test_stale_upload_cleans_new_object(
    client,
    category,
    roles,
    storage,
):
    user, organizer = make_organizer(
        roles,
        suffix="stale",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="stale",
    )

    Event.objects.filter(pk=event.pk).update(version=2)

    response = auth(
        client,
        user,
    ).put(
        f"/api/v1/events/{event.pk}/image",
        {
            "image": image_file(),
        },
        format="multipart",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409
    assert storage._objects == {}


@pytest.mark.django_db
def test_replacing_image_deletes_old_after_commit(
    client,
    category,
    roles,
    storage,
    django_capture_on_commit_callbacks,
):
    user, organizer = make_organizer(
        roles,
        suffix="replace",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="replace",
    )

    old_key = f"events/{organizer.pk}/" f"{event.pk}/old.png"

    storage.upload(
        io.BytesIO(PNG),
        old_key,
    )

    event.image_key = old_key

    event.save(
        update_fields=[
            "image_key",
        ]
    )

    with django_capture_on_commit_callbacks(execute=True):
        response = auth(
            client,
            user,
        ).put(
            f"/api/v1/events/{event.pk}/image",
            {
                "image": image_file(),
            },
            format="multipart",
            HTTP_IF_MATCH='"1"',
        )

    assert response.status_code == 200

    event.refresh_from_db()

    assert event.image_key != old_key
    assert old_key not in storage._objects
    assert event.image_key in storage._objects


@pytest.mark.django_db
def test_owner_can_delete_event_image(
    client,
    category,
    roles,
    storage,
    django_capture_on_commit_callbacks,
):
    user, organizer = make_organizer(
        roles,
        suffix="delete",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="delete",
    )

    key = f"events/{organizer.pk}/" f"{event.pk}/poster.png"

    storage.upload(
        io.BytesIO(PNG),
        key,
    )

    event.image_key = key

    event.save(
        update_fields=[
            "image_key",
        ]
    )

    with django_capture_on_commit_callbacks(execute=True):
        response = auth(
            client,
            user,
        ).delete(
            f"/api/v1/events/{event.pk}/image",
            HTTP_IF_MATCH='"1"',
        )

    assert response.status_code == 204
    assert response["ETag"] == '"2"'

    event.refresh_from_db()

    assert event.image_key == ""
    assert key not in storage._objects


@pytest.mark.django_db
def test_owner_can_get_signed_event_image_url(
    client,
    category,
    roles,
    storage,
):
    user, organizer = make_organizer(
        roles,
        suffix="get-url",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="get-url",
    )

    key = f"events/{organizer.pk}/" f"{event.pk}/poster.png"

    storage.upload(
        io.BytesIO(PNG),
        key,
    )

    event.image_key = key

    event.save(
        update_fields=[
            "image_key",
        ]
    )

    response = auth(
        client,
        user,
    ).get(f"/api/v1/events/{event.pk}/image")

    assert response.status_code == 200
    assert response["ETag"] == '"1"'
    assert response.data["expires_in"] == 300
    assert response.data["url"].startswith("memory://")


@pytest.mark.django_db
def test_signed_local_media_url_serves_file(
    client,
    tmp_path,
    monkeypatch,
):
    local = LocalStorage(tmp_path)

    key = "events/org/event/poster.png"

    local.upload(
        io.BytesIO(PNG),
        key,
    )

    monkeypatch.setattr(
        "apps.catalog.views." "build_object_storage",
        lambda: local,
    )

    url = local.presigned_url(
        key,
        300,
    )

    response = client.get(url)

    assert response.status_code == 200

    body = b"".join(response.streaming_content)

    assert body == PNG
    assert response["Content-Type"] == ("image/png")
