from __future__ import annotations

from pathlib import Path

import pytest

from apps.core.adapters import notifications
from apps.core.adapters.notifications import ConsoleSender, SmtpSender
from apps.core.email_branding import FANID_LOGO_CID, load_fanid_logo_bytes, render_fanid_email_html


@pytest.mark.parametrize(
    ("subject", "body", "expected"),
    [
        (
            "[FANID] Votre compte scanner",
            (
                "Bonjour Nadia,\n\n"
                "Mot de passe temporaire : "
                "Tmp-Example-Only-123!\n\n"
                "Connexion : "
                "https://fanid.example/login\n\n"
                "L’équipe FANID"
            ),
            "Se connecter à FANID",
        ),
        (
            "[FANID] Mot de passe oublié",
            (
                "Bonjour,\n\n"
                "Votre code est :\n\n"
                "123456\n\n"
                "Réinitialisation : "
                "https://fanid.example/"
                "password-reset?token=fake\n\n"
                "L’équipe FANID"
            ),
            "Réinitialiser mon mot de passe",
        ),
        (
            "[FANID] Demande scanner",
            (
                "Bonjour,\n\n"
                "Une demande scanner nécessite "
                "votre attention.\n\n"
                "https://fanid.example/"
                "organizer/scanners\n\n"
                "L’équipe FANID"
            ),
            "Ouvrir l’espace Scanners",
        ),
        (
            "[FANID] Notification",
            ("Bonjour,\n\n" "Votre opération FANID " "est terminée.\n\n" "L’équipe FANID"),
            "Cet e-mail a été envoyé " "automatiquement par FANID.",
        ),
    ],
)
def test_fanid_html_branding_covers_main_email_shapes(
    subject,
    body,
    expected,
):
    rendered = render_fanid_email_html(
        subject=subject,
        body=body,
    )

    assert "<!doctype html>" in rendered
    assert f"cid:{FANID_LOGO_CID}" in rendered
    assert "FANID" in rendered
    assert expected in rendered


def test_links_are_buttons_not_visible_raw_urls():
    url = "https://fanid.example/login"

    rendered = render_fanid_email_html(
        subject="[FANID] Connexion",
        body=f"Connexion : {url}",
    )

    assert f'href="{url}"' in rendered
    assert ">Se connecter à FANID<" in rendered
    assert f">Connexion : {url}<" not in rendered


def test_html_escapes_untrusted_text():
    rendered = render_fanid_email_html(
        subject="<script>alert(1)</script>",
        body="<img src=x onerror=alert(1)>",
    )

    assert "<script>alert(1)</script>" not in rendered
    assert "<img src=x onerror=alert(1)>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "&lt;img" in rendered


def test_otp_is_present_in_email_but_presented_as_security_code():
    rendered = render_fanid_email_html(
        subject="[FANID] Code",
        body=("Votre code de vérification est :\n\n" "123456"),
    )

    assert "123456" in rendered
    assert "Code de vérification FANID" in rendered


def test_logo_asset_is_real_png():
    logo = load_fanid_logo_bytes()

    assert logo.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(logo) > 1000


def test_console_sender_never_passes_email_body_to_logger(
    monkeypatch,
):
    sender = ConsoleSender()
    secret = "Fake-Local-Secret-123456"
    captured = {}

    def fake_warning(message, *, extra):
        captured["message"] = message
        captured["extra"] = extra

    monkeypatch.setattr(
        notifications.logger,
        "warning",
        fake_warning,
    )

    sender.send_email(
        to="scanner@example.test",
        subject="[FANID] Sécurité",
        body=f"Votre code local est {secret}",
    )

    assert captured["message"] == ("notification.console.email")

    assert "body" not in captured["extra"]
    assert secret not in repr(captured)

    assert captured["extra"]["body_length"] > 0

    assert captured["extra"]["has_html"] is True


class _FakeConnection:
    def __init__(self):
        self.messages = []

    def send_messages(self, messages):
        self.messages.extend(messages)
        return len(messages)


def test_smtp_sender_builds_multipart_html_with_inline_logo(
    monkeypatch,
):
    connection = _FakeConnection()

    monkeypatch.setenv(
        "EMAIL_HOST",
        "smtp.example.test",
    )
    monkeypatch.setenv(
        "EMAIL_PORT",
        "587",
    )
    monkeypatch.setenv(
        "EMAIL_USE_TLS",
        "true",
    )
    monkeypatch.setenv(
        "EMAIL_USE_SSL",
        "false",
    )
    monkeypatch.setenv(
        "DEFAULT_FROM_EMAIL",
        "FANID <no-reply@example.test>",
    )
    monkeypatch.delenv(
        "EMAIL_HOST_USER",
        raising=False,
    )
    monkeypatch.delenv(
        "EMAIL_HOST_PASSWORD",
        raising=False,
    )

    monkeypatch.setattr(
        notifications,
        "get_connection",
        lambda **kwargs: connection,
    )

    SmtpSender().send_email(
        to="scanner@example.test",
        subject="[FANID] Invitation",
        body=("Bonjour,\n\n" "Connexion : " "https://fanid.example/login"),
    )

    assert len(connection.messages) == 1

    message = connection.messages[0]

    assert message.body.startswith("Bonjour")
    assert message.alternatives
    assert message.alternatives[0].mimetype == "text/html"

    html_body = message.alternatives[0].content

    assert f"cid:{FANID_LOGO_CID}" in html_body
    assert "Se connecter à FANID" in html_body

    mime = message.message().as_string()

    assert "Content-ID: <fanid-logo>" in mime
    assert "Content-Type: image/png" in mime


def test_all_backend_email_sending_goes_through_notification_adapter():
    apps_root = Path(__file__).resolve().parents[2]

    violations = []

    for path in apps_root.rglob("*.py"):
        parts = set(path.parts)

        if "tests" in parts:
            continue

        if path.name == "notifications.py" and path.parent.name == "adapters":
            continue

        source = path.read_text()

        for forbidden in (
            "send_mail(",
            "EmailMessage(",
            "EmailMultiAlternatives(",
        ):
            if forbidden in source:
                violations.append(f"{path}: {forbidden}")

    assert violations == []
