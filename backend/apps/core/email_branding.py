from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import urlparse

FANID_LOGO_CID = "fanid-logo"

_LOGO_PATH = Path(__file__).resolve().parent / "email_assets" / "fanid-logo.png"

_URL_RE = re.compile(
    r"""https?://[^\s<>"']+""",
    re.IGNORECASE,
)

_OTP_RE = re.compile(r"^\d{6}$")


def load_fanid_logo_bytes() -> bytes:
    return _LOGO_PATH.read_bytes()


def _cta_label(url: str) -> str:
    path = urlparse(url).path.lower()

    if "password-reset" in path:
        return "Réinitialiser mon mot de passe"

    if "forgot-password" in path:
        return "Récupérer mon accès"

    if "/organizer/scanners" in path:
        return "Ouvrir l’espace Scanners"

    if path.endswith("/login") or path == "/login":
        return "Se connecter à FANID"

    if "/organizer" in path:
        return "Ouvrir mon espace organisateur"

    return "Ouvrir FANID"


def _paragraph(value: str) -> str:
    return (
        '<p style="margin:0 0 18px;'
        "font-family:Arial,Helvetica,sans-serif;"
        "font-size:16px;line-height:1.65;"
        'color:#334155;">'
        f"{html.escape(value)}"
        "</p>"
    )


def _secret_box(value: str, *, label: str) -> str:
    return (
        '<div style="margin:20px 0;padding:18px;'
        "border:1px solid #cbd5e1;border-radius:14px;"
        'background:#f8fafc;text-align:center;">'
        '<div style="margin-bottom:8px;'
        "font-family:Arial,Helvetica,sans-serif;"
        "font-size:12px;font-weight:700;"
        "letter-spacing:.08em;text-transform:uppercase;"
        'color:#64748b;">'
        f"{html.escape(label)}"
        "</div>"
        '<div style="font-family:Consolas,Monaco,monospace;'
        "font-size:28px;font-weight:700;"
        "letter-spacing:.12em;word-break:break-all;"
        'color:#173968;">'
        f"{html.escape(value)}"
        "</div>"
        "</div>"
    )


def _button(url: str) -> str:
    safe_url = html.escape(url, quote=True)

    return (
        '<table role="presentation" cellspacing="0" cellpadding="0" '
        'border="0" style="margin:22px 0 26px;">'
        "<tr><td>"
        f'<a href="{safe_url}" '
        'style="display:inline-block;padding:14px 24px;'
        "border-radius:12px;background:#173968;"
        "font-family:Arial,Helvetica,sans-serif;"
        "font-size:15px;font-weight:700;"
        'text-decoration:none;color:#72e6ef;">'
        f"{html.escape(_cta_label(url))}"
        "</a>"
        "</td></tr></table>"
    )


def _body_html(body: str) -> str:
    output: list[str] = []
    previous_non_empty = ""

    for raw_line in body.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        url_matches = list(_URL_RE.finditer(line))

        if url_matches:
            cursor = 0

            for match in url_matches:
                before = line[cursor : match.start()].strip()

                if before:
                    before = before.rstrip(":- ")
                    if before:
                        output.append(_paragraph(before))

                url = match.group(0).rstrip(".,);]}")
                output.append(_button(url))
                cursor = match.end()

            after = line[cursor:].strip()

            if after:
                output.append(_paragraph(after))

            previous_non_empty = line
            continue

        if _OTP_RE.fullmatch(line):
            output.append(
                _secret_box(
                    line,
                    label="Code de vérification FANID",
                )
            )
            previous_non_empty = line
            continue

        lower_line = line.casefold()

        if "mot de passe temporaire" in lower_line and ":" in line:
            label, possible_secret = line.split(":", 1)
            possible_secret = possible_secret.strip()

            output.append(_paragraph(label.strip()))

            if possible_secret:
                output.append(
                    _secret_box(
                        possible_secret,
                        label="Mot de passe temporaire",
                    )
                )

            previous_non_empty = line
            continue

        if (
            previous_non_empty
            and "mot de passe temporaire" in previous_non_empty.casefold()
            and " " not in line
            and len(line) <= 128
        ):
            output.append(
                _secret_box(
                    line,
                    label="Mot de passe temporaire",
                )
            )
            previous_non_empty = line
            continue

        output.append(_paragraph(line))
        previous_non_empty = line

    return "".join(output)


def render_fanid_email_html(
    *,
    subject: str,
    body: str,
) -> str:
    safe_subject = html.escape(subject)

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_subject}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
       style="width:100%;background:#f1f5f9;">
<tr>
<td align="center" style="padding:32px 12px;">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0"
       style="width:100%;max-width:600px;background:#ffffff;border-radius:22px;
              overflow:hidden;border:1px solid #e2e8f0;">
<tr>
<td align="center" style="padding:28px 24px 22px;background:#f8fafc;">
<img src="cid:{FANID_LOGO_CID}"
     width="96"
     height="96"
     alt="FANID"
     style="display:block;width:96px;height:96px;border:0;">
<div style="margin-top:12px;font-family:Arial,Helvetica,sans-serif;
            font-size:13px;font-weight:700;letter-spacing:.12em;
            color:#173968;">
FANID
</div>
</td>
</tr>
<tr>
<td style="padding:32px 32px 26px;">
<h1 style="margin:0 0 24px;font-family:Arial,Helvetica,sans-serif;
           font-size:24px;line-height:1.3;color:#173968;">
{safe_subject}
</h1>
{_body_html(body)}
</td>
</tr>
<tr>
<td style="padding:22px 32px;background:#f8fafc;border-top:1px solid #e2e8f0;">
<p style="margin:0;font-family:Arial,Helvetica,sans-serif;
          font-size:12px;line-height:1.6;color:#64748b;">
Cet e-mail a été envoyé automatiquement par FANID.
Ne communiquez jamais vos codes de sécurité ou mots de passe temporaires.
</p>
</td>
</tr>
</table>
</td>
</tr>
</table>
</body>
</html>"""


__all__ = [
    "FANID_LOGO_CID",
    "load_fanid_logo_bytes",
    "render_fanid_email_html",
]
