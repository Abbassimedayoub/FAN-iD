"""
Limitations de debit sur mesure du contexte identity.

Deux limites ne peuvent pas etre exprimees correctement avec les throttles
standards de DRF :

- connexion : limitation par compte avant authentification ;
- rafraichissement : limitation par session portee par le refresh token.

Le plan impose :

- login : 5/min/IP + 60/h/compte ;
- refresh : 30/h/session.
"""

from __future__ import annotations

import hashlib
from typing import Any

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

from .constants import CLIENT_WEB
from .tokens import TokenInvalidError, TokenType, decode_token


class LoginAccountRateThrottle(SimpleRateThrottle):
    """
    Plafonne les tentatives visant UNE MEME adresse, quelle que soit l origine.

    L appelant n est pas encore authentifie lors d une connexion. Une limitation
    par IP seule ne suffit pas contre une attaque distribuee visant le meme
    compte : ce throttle ajoute donc un compteur par adresse de compte.

    L adresse n est jamais stockee en clair dans le cache. Elle est normalisee,
    puis transformee en SHA-256 avant d etre utilisee comme identifiant.
    """

    scope = "login_account"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        email = (request.data or {}).get("email") if hasattr(request, "data") else None

        if not isinstance(email, str) or not email.strip():
            return None

        digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()

        return self.cache_format % {
            "scope": self.scope,
            "ident": digest,
        }


class RefreshSessionRateThrottle(SimpleRateThrottle):
    """
    Plafonne les rotations a UNE MEME session.

    Le refresh endpoint ne peut pas utiliser UserRateThrottle : son access token
    peut etre expire et la vue desactive donc volontairement l authentification
    DRF.

    Le refresh token porte en revanche le claim `sid`, identifiant stable de la
    session. C est cet identifiant qui constitue la cle du compteur.

    La source du refresh respecte exactement le contrat HTTP :

    - client=web    -> cookie HttpOnly ;
    - client=mobile -> corps de la requete.

    Un token absent ou invalide n est pas transforme ici en erreur metier :
    le throttle se retire et laisse la vue/service produire le 400/401 prevu.
    Le throttle ne doit jamais modifier la semantique d authentification.
    """

    scope = "refresh"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        if not hasattr(request, "data"):
            return None

        data = request.data or {}
        client = data.get("client")

        if client == CLIENT_WEB:
            raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        else:
            raw = data.get("refresh")

        if not isinstance(raw, str) or not raw.strip():
            return None

        try:
            claims = decode_token(
                raw.strip(),
                expected_type=TokenType.REFRESH,
            )
        except TokenInvalidError:
            return None

        sid = claims.get("sid")
        if not isinstance(sid, str) or not sid.strip():
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": sid.strip(),
        }


class DeviceResetAccountRateThrottle(LoginAccountRateThrottle):
    """
    Plafonne les demandes de reinitialisation visant UN MEME compte.

    Herite du hachage et de la normalisation de l adresse — un seul endroit ou
    cette logique existe. Seule la portee change.

    **C est l axe qui protege la victime.** Une demande de reinitialisation
    envoie un courriel : sans plafond par compte, mille adresses IP suffisent a
    noyer la boite d une personne ciblee, et le quota par origine n y peut rien.
    Dix par heure laisse plusieurs tentatives legitimes tout en conservant
    une protection contre le harcelement par courriel.
    """

    scope = "device_reset_account"


class PasswordResetAccountRateThrottle(LoginAccountRateThrottle):
    """
    Protège une boîte précise contre les demandes distribuées.

    L'adresse reste uniquement sous forme de SHA-256 dans le cache.
    """

    scope = "password_reset_account"
