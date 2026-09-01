from django.conf import settings
from django.test import override_settings

ORIGIN = "http://localhost:5173"


def test_cors_contract_allows_if_match_and_exposes_etag():
    allowed = {header.lower() for header in settings.CORS_ALLOW_HEADERS}
    exposed = {header.lower() for header in settings.CORS_EXPOSE_HEADERS}

    assert "if-match" in allowed
    assert "etag" in exposed


@override_settings(CORS_ALLOWED_ORIGINS=[ORIGIN])
def test_cors_preflight_accepts_if_match(client):
    response = client.options(
        "/api/v1/admin/organizers/00000000-0000-4000-8000-000000000001/approve",
        HTTP_ORIGIN=ORIGIN,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type, if-match",
    )

    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == ORIGIN

    allowed = {header.strip().lower() for header in response["Access-Control-Allow-Headers"].split(",")}

    assert "if-match" in allowed

    exposed = {header.strip().lower() for header in response["Access-Control-Expose-Headers"].split(",")}

    assert "etag" in exposed
