"""
Le refus est le defaut du projet.

Ce fichier garde une decision de configuration, pas un comportement de code. Ce
genre de reglage se defait sans bruit : quelqu un debogue un 403, remet
`IsAuthenticated` « le temps de tester », et l oublie. Un test le rattrape ; une
ligne de documentation, non.
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
    """Vue dont on a « oublie » `permission_classes` — le cas a rattraper."""

    def get(self, request):  # pragma: no cover - le refus intervient avant
        return Response({"leaked": True})


def test_the_project_default_permission_is_deny_all():
    assert api_settings.DEFAULT_PERMISSION_CLASSES == [DenyAll]


def test_a_view_without_an_explicit_policy_refuses_even_an_authenticated_caller():
    """
    Le defaut precedent, `IsAuthenticated`, etait deja meilleur que celui de DRF
    (`AllowAny`) — mais il laisse passer TOUT compte connecte. Sur une
    plateforme ou supporters, organisateurs, scanners et administrateurs
    partagent la meme API, « etre connecte » n est pas une autorisation : un
    point de terminaison d administration dont on aurait oublie la politique
    serait accessible a un compte cree en trente secondes.
    """
    request = APIRequestFactory().get("/oubli")
    # Double de test plutot qu un vrai `User` : ce fichier appartient a `core`,
    # qui ne doit importer AUCUN contexte borne (ADR-S-01, contrat verifie par
    # import-linter). Le `cast` ne masque pas un defaut — il declare que DRF n a
    # besoin ici que de `is_authenticated`, la ou sa signature exige un modele.
    force_authenticate(request, user=cast(AbstractBaseUser, SimpleNamespace(is_authenticated=True, pk=1)))

    response = _ViewWithoutAnyPolicy.as_view()(request)

    assert response.status_code == 403


def test_the_openapi_schema_stays_reachable_without_authentication():
    """
    Garde-fou de la porte G1.

    `drf-spectacular` sert son schema avec ses PROPRES permissions
    (`SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"]`), pas avec le defaut du projet.
    Le passage a `DenyAll` ne devrait donc rien casser — mais c est exactement le
    genre de « ne devrait pas » qui merite une verification, parce que la panne
    se manifesterait comme un echec de la porte OpenAPI sans rapport apparent
    avec un changement de permissions.
    """
    response = APIClient().get("/api/v1/schema/")

    assert response.status_code == 200


@pytest.mark.parametrize("path", ["/api/v1/health", "/api/v1/health/ready"])
def test_the_platform_probes_stay_reachable_without_authentication(path, db):
    """
    Une sonde qui repond 403 fait redemarrer le service en boucle.

    Les sondes declarent leur propre `AllowAny` ; ce test verifie que le
    changement de defaut ne les a pas emportees.
    """
    response = APIClient().get(path)

    assert response.status_code in (200, 503)
    assert response.status_code != 403


def test_the_sprint_0_policy_shell_no_longer_exists():
    """
    `apps.core.policy.engine.PolicyEngine` etait une coquille du Sprint 0 qui
    levait `NotImplementedError`.

    Elle est supprimee au profit de `apps.identity.authz`. La raison n est pas
    le menage : deux endroits ou une autorisation POURRAIT se decider, c est un
    de trop. Tant que la coquille existait, un developpeur pouvait l implementer
    de bonne foi et creer une seconde source de verite — sans jamais croiser la
    matrice de `rules.py`.
    """
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("apps.core.policy.engine")
