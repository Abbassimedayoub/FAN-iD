"""
Primitives de jeton — la seule frontiere cryptographique du projet.

Deux fonctions, et rien d autre. Tout ce qui touche a la signature ou a la
verification d un JWT passe par ici : c est le seul endroit ou une erreur de
cette famille peut exister, donc le seul endroit a relire quand on doute.

**Pourquoi PyJWT et pas `djangorestframework-simplejwt`** (fiche de dependance
§64) : le plan v2 a remplace la liste de revocation de simplejwt par la table
`session`. Il ne restait de la bibliotheque que des vues et des serialiseurs
inutilises, plus un SECOND registre de revocation — exactement le defaut que la
suppression de `core/policy` visait a eliminer. simplejwt dependant lui-meme de
PyJWT, on retire une couche, pas une protection.

**Les quatre pieges de la famille JWT, et leur parade ici.** Chacun a son test.

1. `alg: none` — un jeton dont l en-tete declare « aucune signature ». Parade :
   `algorithms=[...]` explicite au decodage. PyJWT l EXIGE, mais la liste doit
   etre juste.
2. Confusion d algorithme — un jeton HS512, ou HS256 signe avec une cle publique
   RSA. Parade : un SEUL algorithme accepte, celui des reglages.
3. Absence de verification d expiration, ou tolerance trop large. Parade :
   `exp` obligatoire, `leeway` explicite et borne.
4. **Confusion de type** — un refresh presente a la place d un access, ou
   l inverse. C est le plus grave et le moins connu : il contourne la rotation
   ENTIERE, puisque le jeton a longue duree de vie devient utilisable comme
   jeton d acces. Parade : un claim `token_type` obligatoire, verifie par
   comparaison stricte au type attendu par l APPELANT.

**`token_type` et non `typ`** : `typ` est deja un champ d en-tete JOSE valant
« JWT ». Reutiliser ce nom dans la charge utile creerait deux champs homonymes a
deux endroits differents — la premiere confusion d un lecteur presse.
"""

from __future__ import annotations

import datetime
import uuid
from enum import StrEnum
from typing import Any

import jwt
from django.conf import settings

from apps.core.exceptions import AuthError


class TokenType(StrEnum):
    """Type porte par le claim `token_type`, et verifie au decodage."""

    ACCESS = "access"
    REFRESH = "refresh"


class TokenInvalidError(AuthError):
    """
    401 — jeton illisible, mal signe, de mauvais type ou incomplet.

    Un SEUL code pour tous ces cas, deliberement. Distinguer « signature
    invalide » de « type incorrect » renseignerait un attaquant sur l etat
    d avancement de sa forge. Le motif precis part dans les journaux.
    """

    default_code = "TOKEN_INVALID"
    default_message = "Jeton invalide."


class TokenExpiredError(AuthError):
    """
    401 — jeton expire.

    Distingue de `TOKEN_INVALID`, contrairement au reste : le client DOIT savoir
    qu il faut rafraichir plutot que se reconnecter. Et l information ne sert a
    rien a un attaquant — un jeton expire est un jeton qu il possede deja.
    """

    default_code = "TOKEN_EXPIRED"
    default_message = "Jeton expire."


class TokenReuseDetectedError(AuthError):
    """
    401 — un refresh deja tourne a ete rejoue.

    Motif DISTINCT, contrairement a la regle d opacite qui vaut ailleurs. Deux
    raisons : le client legitime doit comprendre qu il faut se reconnecter et
    non reessayer, et surtout la metrique
    `fanid_auth_token_reuse_detected_total` doit pouvoir compter cet evenement
    precis — toute valeur superieure a zero merite une inspection (plan §5.4).

    Ce que cette erreur revele a un attaquant, il le sait deja : il vient de
    rejouer un jeton qu il possede.
    """

    default_code = "TOKEN_REUSE_DETECTED"
    default_message = "Ce jeton a deja ete utilise. La session a ete revoquee."


def _algorithm() -> str:
    return str(settings.JWT_ALGORITHM)


def _signing_key() -> str:
    """
    Cle de signature — JAMAIS `SECRET_KEY`.

    En HS256 la cle signe ET verifie. La partager avec Django transformerait
    toute fuite de `SECRET_KEY` — un `settings.py` verse par erreur dans un
    ticket, une variable exposee par une page d erreur — en usurpation
    d identite de n importe quel compte, y compris administrateur. Deux secrets
    distincts, deux rayons d explosion distincts.
    """
    return str(settings.JWT_SIGNING_KEY)


def encode_token(
    *,
    token_type: TokenType,
    subject: uuid.UUID,
    lifetime: datetime.timedelta,
    claims: dict[str, Any] | None = None,
    issued_at: datetime.datetime,
) -> tuple[str, uuid.UUID, datetime.datetime]:
    """
    Signe un jeton et renvoie `(jeton, jti, expiration)`.

    Le `jti` et l expiration sont RENVOYES plutot que relus du jeton : l appelant
    doit les enregistrer dans `identity_session`, et redecoder ce qu on vient
    d ecrire pour retrouver ses propres valeurs serait a la fois inutile et une
    occasion de divergence.

    `issued_at` est un PARAMETRE, pas `timezone.now()` appele ici. La fonction
    reste ainsi deterministe : un test peut fabriquer un jeton emis il y a huit
    jours sans manipuler l horloge du systeme, et une paire access/refresh emise
    au meme instant porte reellement le meme `iat`.
    """
    jti = uuid.uuid4()
    expires_at = issued_at + lifetime
    payload: dict[str, Any] = {
        **(claims or {}),
        "token_type": str(token_type),
        "sub": str(subject),
        "jti": str(jti),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": str(settings.JWT_ISSUER),
    }
    token = jwt.encode(payload, _signing_key(), algorithm=_algorithm())
    return token, jti, expires_at


#: Claims exiges dans TOUT jeton. Un jeton auquel il manque `exp` serait
#: eternel ; sans `jti`, il serait irrevocable ; sans `token_type`, il serait
#: interchangeable. PyJWT ne verifie la presence d un claim que si on la demande.
REQUIRED_CLAIMS = ("exp", "iat", "jti", "sub", "token_type", "iss")


def decode_token(raw: str, *, expected_type: TokenType) -> dict[str, Any]:
    """
    Verifie un jeton et renvoie ses claims.

    `expected_type` est OBLIGATOIRE et sans valeur par defaut : un appelant ne
    peut pas oublier de preciser ce qu il attend. C est la parade au piege n° 4,
    et un defaut par defaut la rendrait facultative.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            raw,
            _signing_key(),
            # Liste EXPLICITE, reduite a l algorithme configure. C est cette
            # ligne qui ferme `alg: none` et la confusion d algorithme : PyJWT
            # refuse tout en-tete annoncant autre chose, sans meme verifier la
            # signature.
            algorithms=[_algorithm()],
            issuer=str(settings.JWT_ISSUER),
            leeway=int(settings.JWT_LEEWAY_SECONDS),
            options={"require": list(REQUIRED_CLAIMS)},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except jwt.PyJWTError as exc:
        # Tout le reste — signature fausse, en-tete bricole, claim manquant,
        # emetteur inattendu — donne le MEME code. Le detail est un cadeau fait
        # a celui qui forge.
        raise TokenInvalidError() from exc

    if payload.get("token_type") != str(expected_type):
        raise TokenInvalidError()

    return payload
