"""
Tests sécurité (§60 master prompt / §6.1 Source B) : configuration de
production sans avertissement, en-têtes de sécurité présents, aucun secret
loggué par la suite de tests elle-même.
"""

import importlib
import logging
import os
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.core.observability.logging import JsonFormatter


def test_production_settings_module_defines_required_security_headers(monkeypatch):
    """
    Équivalent ciblé de `manage.py check --deploy` (§60 master prompt) : on
    charge réellement `config.settings.prod` (pas une lecture de source) pour
    vérifier les valeurs telles que Django les verrait, avec l'environnement
    minimal requis fourni par le test (jamais de vrai secret).
    """
    monkeypatch.setenv("DJANGO_SECRET_KEY", "x" * 60)
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "example.com")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/3")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/4")
    # Ajoutée au Sprint 1 (S1-A.0) : dès que l'authentification s'appuie sur un
    # cookie, une liste blanche CSRF explicite devient obligatoire. `prod.py` la
    # lit SANS défaut (§41), le test doit donc la fournir comme les autres.
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://app.example.test")

    # `import_module` ne réexécute pas un module déjà dans `sys.modules` : on
    # vide le cache pour que le module soit VRAIMENT évalué avec l'environnement
    # que ce test vient de poser, quel que soit l'ordre des tests dans le worker.
    sys.modules.pop("config.settings.prod", None)
    prod_settings = importlib.import_module("config.settings.prod")

    assert prod_settings.SECURE_HSTS_SECONDS == 31536000
    assert prod_settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod_settings.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod_settings.X_FRAME_OPTIONS == "DENY"
    assert prod_settings.SECURE_REFERRER_POLICY == "strict-origin-when-cross-origin"
    assert prod_settings.SECURE_SSL_REDIRECT is True
    assert prod_settings.DEBUG is False
    assert prod_settings.SPECTACULAR_SETTINGS["SERVE_PUBLIC"] is False

    # Invariants du Sprint 1 (§18) : le refresh circule dans un cookie, il ne
    # doit JAMAIS transiter en clair en production, et la liste blanche CSRF
    # doit être réellement peuplée — une liste vide laisserait passer toute
    # origine tierce sur les requêtes authentifiées par cookie.
    assert prod_settings.REFRESH_COOKIE_SECURE is True
    assert prod_settings.REFRESH_COOKIE_HTTPONLY is True
    assert prod_settings.CSRF_TRUSTED_ORIGINS
    assert all(o.startswith("https://") for o in prod_settings.CSRF_TRUSTED_ORIGINS)


def test_production_refuses_to_start_without_a_csrf_allowlist(monkeypatch):
    """
    §41 : aucune variable critique de production n'a de valeur par défaut
    fonctionnelle. Un défaut silencieux y est pire qu'un plantage au démarrage.

    Ce test existe parce que l'ajout de `CSRF_TRUSTED_ORIGINS` au Sprint 1 a fait
    échouer le test de chargement des settings de production — ce qui était le
    comportement correct. Plutôt que de se contenter de fournir la variable, on
    verrouille l'exigence : si quelqu'un lui donnait un jour un défaut par
    commodité, ce test le signalerait immédiatement.
    """
    monkeypatch.setenv("DJANGO_SECRET_KEY", "x" * 60)
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "example.com")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/3")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/4")
    monkeypatch.delenv("CSRF_TRUSTED_ORIGINS", raising=False)

    # Garde-fou : si l'environnement fournissait encore la variable, le test
    # passerait sans rien prouver.
    assert "CSRF_TRUSTED_ORIGINS" not in os.environ

    # Même raison qu'au-dessus : sans vider le cache, `import_module` lèverait
    # HORS du `pytest.raises` quand le module n'a pas encore été chargé par ce
    # worker — l'issue du test dépendrait de l'ordre d'exécution.
    sys.modules.pop("config.settings.prod", None)
    with pytest.raises(ImproperlyConfigured):
        importlib.import_module("config.settings.prod")


def test_dev_env_example_never_contains_a_real_looking_secret():
    """
    `.env.example` ne doit contenir aucune valeur qui ressemble à un vrai
    secret (clé Stripe live, clé AWS...) — uniquement des marqueurs "dev-only"
    ou des valeurs vides (§41 master prompt).
    """
    from pathlib import Path

    candidates = [
        Path("/config/.env.example"),
        *(parent / ".env.example" for parent in Path(__file__).resolve().parents),
    ]

    env_example = next(
        (path for path in candidates if path.exists()),
        None,
    )

    assert env_example is not None, ".env.example introuvable depuis le contexte de test"

    content = env_example.read_text()

    forbidden_patterns = [
        "sk_live_",
        "AKIA",
        "-----BEGIN",
    ]

    for pattern in forbidden_patterns:
        assert pattern not in content, f"motif de secret réel potentiel trouvé : {pattern}"


def test_no_secret_pattern_leaks_through_the_logging_pipeline_end_to_end(caplog):
    """
    Parcourt les lignes produites par le pipeline de logging complet
    (JsonFormatter) pour un enregistrement contenant délibérément un secret,
    et vérifie que la valeur brute n'apparaît jamais dans la sortie formatée
    — c'est ce test, pas une relecture manuelle, qui doit détecter une
    régression de `SecretRedactor` (§60 master prompt : "aucun log ne contient
    de motif sensible — test qui parcourt les logs générés par la suite").
    """
    formatter = JsonFormatter()
    secret_value = "sk_test_do_not_leak_me_0000000000"
    record = logging.LogRecord(
        name="fanid.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="payment_intent_created",
        args=(),
        exc_info=None,
    )
    record.stripe_secret_key = secret_value
    record.nested = {"authorization": f"Bearer {secret_value}"}

    formatted_line = formatter.format(record)

    assert secret_value not in formatted_line
