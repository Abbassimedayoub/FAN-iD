"""
Classe d authentification DRF — `Authorization: Bearer <access>`.

C est le point ou un jeton devient un utilisateur. Trois verifications, dans cet
ordre : la SIGNATURE (`tokens.py`), la SESSION (revocation), l APPAREIL
(`DeviceBindingService`).

## Pourquoi une requete SQL par appel, et pourquoi c est le bon choix

On pourrait fabriquer un utilisateur a partir des seuls claims — zero requete.
C est ce que font la plupart des integrations JWT, et c est precisement ce qui
rend leurs jetons IRREVOCABLES avant expiration.

Ici, la session est relue a chaque appel. Cout : une recherche par cle primaire
sur un index, quelques centaines de microsecondes. Gain : une revocation prend
effet IMMEDIATEMENT — deconnexion, changement de mot de passe, detection de
reutilisation de refresh. Sans cette lecture, la table `session` construite au
lot S1-A.1b ne servirait qu au rafraichissement, et un jeton vole resterait
valable quinze minutes apres qu on a detecte le vol.

La lecture charge `user`, `role` et `device` en une seule requete : le controle
d autorisation qui suit n en declenche aucune autre.

## Le claim `role` n autorise RIEN

Il voyage dans le jeton pour le CLIENT — afficher le bon menu sans un appel
supplementaire. Le serveur, lui, lit `user.role_id` sur l utilisateur charge
(`authz/context.py`). La distinction n est pas cosmetique : un role modifie en
base prend effet au prochain appel, pas au prochain rafraichissement. Un test
change le role d un compte apres emission du jeton et verifie que la decision
d autorisation suit la BASE, pas le jeton.

## L appareil est verifie ici, pas dans un middleware

Un middleware s execute avant l authentification de DRF : il devrait donc
decoder le jeton lui-meme, et le systeme aurait deux endroits qui verifient une
signature. Le plan parlait d un middleware ; le placer ici respecte l intention
— `did` controle a chaque requete — sans dupliquer la frontiere
cryptographique.
"""

from __future__ import annotations

import functools
import logging
import uuid
from typing import Any

from rest_framework.authentication import BaseAuthentication, get_authorization_header

from .locks import build_device_lock
from .models import Session
from .services.devices import DeviceBindingService
from .tokens import TokenInvalidError, TokenType, decode_token

logger = logging.getLogger("fanid.identity")

AUTH_SCHEME = b"bearer"


@functools.lru_cache(maxsize=1)
def default_binding_service() -> DeviceBindingService:
    """
    Service partage par tout le processus.

    Mis en cache parce qu il porte un client Redis : en fabriquer un par requete
    ouvrirait une connexion par requete. Le client lui-meme se connecte
    paresseusement, donc ce cache n empeche pas le processus de demarrer quand
    Redis est indisponible.
    """
    return DeviceBindingService(lock=build_device_lock())


class JWTAuthentication(BaseAuthentication):
    """Resout l utilisateur a partir d un jeton d acces."""

    def __init__(self, binding_service: DeviceBindingService | None = None) -> None:
        # DRF instancie les classes d authentification SANS argument. Le
        # parametre n existe que pour les tests, qui injectent un verrou en
        # memoire plutot que Redis.
        self._binding = binding_service

    @property
    def binding(self) -> DeviceBindingService:
        return self._binding or default_binding_service()

    def authenticate_header(self, request: Any) -> str:
        """Renvoye avec un 401 : indique au client le schema attendu."""
        return 'Bearer realm="api"'

    def authenticate(self, request: Any) -> tuple[Any, dict[str, Any]] | None:
        raw = self._extract_token(request)
        if raw is None:
            # Aucun en-tete `Bearer` : ce n est PAS une erreur. DRF essaiera les
            # autres classes d authentification, puis traitera la requete comme
            # anonyme. Lever ici casserait tous les points de terminaison
            # publics — l inscription en premier.
            return None

        claims = decode_token(raw, expected_type=TokenType.ACCESS)
        session = self._load_session(claims)
        user = session.user

        if not user.is_active or user.anonymized_at is not None:
            # Un compte desactive ou anonymise garde des jetons valides jusqu a
            # leur expiration. On refuse ici, sans motif distinct : le detail ne
            # servirait qu a confirmer l existence du compte.
            raise TokenInvalidError()

        self.binding.assert_matches(user=user, device_id=claims.get("did"))

        # Niveau d authentification : lu sur la SESSION, pas sur le jeton. Une
        # elevation (verification renforcee) met a jour la session ; le jeton
        # emis avant, lui, porte encore l ancien niveau. Lire la session fait
        # prendre effet l elevation immediatement, et surtout empeche qu une
        # RETROGRADATION soit ignoree.
        request.auth_level = session.auth_level
        request.session_id = session.pk

        return (user, claims)

    # -- details ------------------------------------------------------------

    @staticmethod
    def _extract_token(request: Any) -> str | None:
        header = get_authorization_header(request).split()
        if not header or header[0].lower() != AUTH_SCHEME:
            return None
        if len(header) != 2:
            # `Bearer` seul, ou suivi de plusieurs mots : l intention d utiliser
            # un jeton est claire, la forme ne l est pas. On refuse plutot que
            # de retomber en anonyme, sinon l appelant recevrait un 403
            # incomprehensible au lieu d un 401 explicite.
            raise TokenInvalidError()
        try:
            return header[1].decode()
        except UnicodeDecodeError as exc:
            raise TokenInvalidError() from exc

    def _load_session(self, claims: dict[str, Any]) -> Session:
        """
        Charge la session active designee par `sid`, avec tout ce dont la suite
        a besoin.

        `active()` porte les DEUX conditions — ni revoquee, ni expiree. Ne
        filtrer que sur `revoked_at` laisserait passer une session dont le
        refresh a depasse sa duree de vie ; ne filtrer que sur `expires_at`
        laisserait passer une session revoquee pour reutilisation de jeton,
        c est-a-dire exactement le scenario de vol que la revocation de famille
        est censee fermer.
        """
        try:
            # Converti AVANT la requete : Django leve `ValidationError` — donc
            # une 500 — sur un UUID mal forme passe a un `UUIDField`. Un jeton
            # signe par nous n en contient pas, mais « ne devrait jamais » n est
            # pas une garantie.
            session_id = uuid.UUID(str(claims.get("sid")))
        except (TypeError, ValueError) as exc:
            raise TokenInvalidError() from exc

        session = (
            Session.objects.active()
            .select_related("user", "user__role", "device")
            .filter(pk=session_id)
            .first()
        )
        if session is None:
            # Session revoquee, expiree, ou identifiant inconnu : meme reponse.
            # Distinguer « revoquee » de « inconnue » apprendrait a un attaquant
            # que son jeton a ete repere.
            logger.info("auth.token.session_not_active")
            raise TokenInvalidError()
        return session
