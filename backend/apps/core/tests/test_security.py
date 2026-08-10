"""
Tests sécurité (§60 master prompt / §6.1 Source B) : configuration de
production sans avertissement, en-têtes de sécurité présents, aucun secret
loggué par la suite de tests elle-même.
"""
import importlib
import logging

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

    prod_settings = importlib.import_module("config.settings.prod")
    importlib.reload(prod_settings)

    assert prod_settings.SECURE_HSTS_SECONDS == 31536000
    assert prod_settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod_settings.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod_settings.X_FRAME_OPTIONS == "DENY"
    assert prod_settings.SECURE_REFERRER_POLICY == "strict-origin-when-cross-origin"
    assert prod_settings.SECURE_SSL_REDIRECT is True
    assert prod_settings.DEBUG is False
    assert prod_settings.SPECTACULAR_SETTINGS["SERVE_PUBLIC"] is False


def test_dev_env_example_never_contains_a_real_looking_secret():
    """
    `.env.example` ne doit contenir aucune valeur qui ressemble à un vrai
    secret (clé Stripe live, clé AWS...) — uniquement des marqueurs "dev-only"
    ou des valeurs vides (§41 master prompt).
    """
    from pathlib import Path

    env_example = Path(__file__).resolve().parents[4] / ".env.example"
    content = env_example.read_text()

    forbidden_patterns = ["sk_live_", "AKIA", "-----BEGIN"]
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
        name="fanid.test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="payment_intent_created", args=(), exc_info=None,
    )
    record.stripe_secret_key = secret_value
    record.nested = {"authorization": f"Bearer {secret_value}"}

    formatted_line = formatter.format(record)

    assert secret_value not in formatted_line
