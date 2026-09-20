"""
Deny-by-default is a project configuration invariant.

This test protects that configuration decision from accidental relaxation during
debugging or refactoring.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import cast

import pytest
from django.contrib.auth.base_user import AbstractBaseUser
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.core.permissions import DenyAll


class _ViewWithoutAnyPolicy(APIView):
    """View that intentionally omits `permission_classes`, the case the default must catch."""

    def get(self, request):  # pragma: no cover - le refus intervient avant
        return Response({"leaked": True})


def test_the_project_default_permission_is_deny_all():
    assert api_settings.DEFAULT_PERMISSION_CLASSES == [DenyAll]


def test_a_view_without_an_explicit_policy_refuses_even_an_authenticated_caller():
    """Authenticated is not equivalent to authorized; a view with no explicit policy must still be denied."""
    request = APIRequestFactory().get("/oubli")
    # Use a test double instead of a real User so core tests keep bounded-context
    # independence. DRF only needs the is_authenticated attribute here.
    force_authenticate(request, user=cast(AbstractBaseUser, SimpleNamespace(is_authenticated=True, pk=1)))

    response = _ViewWithoutAnyPolicy.as_view()(request)

    assert response.status_code == 403


def test_the_openapi_schema_stays_reachable_without_authentication():
    """Guard that the OpenAPI schema endpoint keeps using its explicit serve permissions despite the project-wide deny default."""
    response = APIClient().get("/api/v1/schema/")

    assert response.status_code == 200


@pytest.mark.parametrize("path", ["/api/v1/health", "/api/v1/health/ready"])
def test_the_platform_probes_stay_reachable_without_authentication(path, db):
    """Health probes must remain publicly reachable through their explicit AllowAny configuration."""
    response = APIClient().get(path)

    assert response.status_code in (200, 503)
    assert response.status_code != 403


def test_the_sprint_0_policy_shell_no_longer_exists():
    """The old core policy shell must stay removed so identity authorization remains the single policy source of truth."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("apps.core.policy.engine")
