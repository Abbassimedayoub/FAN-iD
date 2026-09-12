from __future__ import annotations

import datetime
import json
from urllib.parse import quote

import pytest
from django.test import Client
from django.utils import timezone


@pytest.fixture
def sql_test_user(db, django_user_model, roles):
    return django_user_model.objects.create_user(
        email="sql-security@example.test",
        password="SafePassword123!",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


def assert_no_database_error_leak(response) -> None:
    body = response.content.decode(
        "utf-8",
        errors="replace",
    ).lower()

    forbidden = (
        "traceback",
        "django.db",
        "psycopg",
        "syntax error at or near",
        "sqlstate",
        "relation ",
        "programmingerror",
        "operationalerror",
    )

    for marker in forbidden:
        assert marker not in body, (
            marker,
            response.status_code,
            body,
        )


@pytest.mark.parametrize(
    "payload",
    [
        "' OR '1'='1",
        "1; SELECT pg_sleep(1)--",
        "00000000-0000-0000-0000-000000000000' UNION SELECT NULL--",
    ],
)
def test_catalog_query_rejects_sql_injection_without_database_leak(
    payload,
):
    response = Client().get(
        "/api/v1/catalog/events",
        {"category_id": payload},
    )

    assert response.status_code == 400
    assert_no_database_error_leak(response)


@pytest.mark.parametrize(
    "payload",
    [
        "' OR '1'='1' --",
        "'; DROP TABLE identity_user; --",
        "' UNION SELECT 'authenticated' --",
    ],
)
def test_login_password_sql_injection_never_authenticates(
    sql_test_user,
    payload,
):
    response = Client().post(
        "/api/v1/auth/login",
        data=json.dumps(
            {
                "email": sql_test_user.email,
                "password": payload,
                "client": "web",
            }
        ),
        content_type="application/json",
        REMOTE_ADDR="203.0.113.50",
    )

    assert response.status_code in {400, 401}
    assert b'"access"' not in response.content
    assert_no_database_error_leak(response)


def test_reservation_body_rejects_sql_injection_uuid(
    sql_test_user,
):
    client = Client()
    client.force_login(sql_test_user)

    response = client.post(
        "/api/v1/orders/reservations",
        data=json.dumps(
            {
                "items": [
                    {
                        "ticket_category_id": ("00000000-0000-0000-0000-000000000000" "' OR '1'='1"),
                        "quantity": 1,
                    }
                ]
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert_no_database_error_leak(response)


def test_uuid_path_sql_injection_never_reaches_order_lookup(
    sql_test_user,
):
    client = Client()
    client.force_login(sql_test_user)

    payload = quote(
        "00000000-0000-0000-0000-000000000000' OR '1'='1",
        safe="",
    )

    response = client.get(f"/api/v1/orders/{payload}")

    assert response.status_code == 404
    assert_no_database_error_leak(response)
