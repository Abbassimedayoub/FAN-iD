"""
Attaques sur les primitives de jeton.

Ces tests ne verifient pas que « ca marche » — un aller-retour reussi ne prouve
presque rien. Ils tentent de FORGER des jetons que le systeme doit refuser. Une
implementation JWT naive passe l aller-retour et tombe sur chacun des cas
ci-dessous.

Aucune base de donnees : ce sont des fonctions pures, elles s executent en
millisecondes. C est ce qui permet d en ecrire beaucoup.
"""

from __future__ import annotations

import datetime
import uuid

import jwt
import pytest

from apps.identity.tokens import (
    REQUIRED_CLAIMS,
    TokenExpiredError,
    TokenInvalidError,
    TokenType,
    decode_token,
    encode_token,
)

SUBJECT = uuid.UUID("11111111-1111-4111-8111-111111111111")
ACCESS_LIFETIME = datetime.timedelta(minutes=15)
REFRESH_LIFETIME = datetime.timedelta(days=7)


def now() -> datetime.datetime:
    """
    L instant courant, et non une date figee.

    Une date d emission constante paraissait plus deterministe — elle rend en
    realite la suite dependante du jour ou on la lance : passe l echeance
    codee en dur, tous les jetons naissent expires. Le determinisme vient ici
    des DECALAGES explicites passes en parametre, pas d une horloge gelee.
    """
    return datetime.datetime.now(datetime.timezone.utc)


def issue(token_type: TokenType = TokenType.ACCESS, *, at=None, lifetime=ACCESS_LIFETIME, **claims):
    return encode_token(
        token_type=token_type,
        subject=SUBJECT,
        lifetime=lifetime,
        claims=claims,
        issued_at=at or now(),
    )


# ===========================================================================
# Aller-retour nominal
# ===========================================================================


def test_an_access_token_round_trips_with_its_business_claims(settings):
    token, jti, expires_at = issue(role="FAN", did="d-1", sid="s-1", auth_level=1)

    claims = decode_token(token, expected_type=TokenType.ACCESS)

    assert claims["sub"] == str(SUBJECT)
    assert claims["role"] == "FAN"
    assert claims["auth_level"] == 1
    assert claims["jti"] == str(jti)
    assert claims["exp"] == int(expires_at.timestamp())


def test_the_identifier_and_expiry_are_returned_rather_than_re_read(settings):
    """
    L appelant enregistre `jti` et `expires_at` dans `identity_session`.

    Les renvoyer evite de redecoder ce qu on vient d ecrire pour retrouver ses
    propres valeurs — inutile, et une occasion de divergence entre ce qui est
    signe et ce qui est stocke.
    """
    moment = now()
    token, jti, expires_at = issue(at=moment, lifetime=REFRESH_LIFETIME)

    assert expires_at == moment + REFRESH_LIFETIME
    assert decode_token(token, expected_type=TokenType.ACCESS)["jti"] == str(jti)


def test_two_tokens_issued_in_the_same_instant_have_different_identifiers(settings):
    """Sans cela, deux sessions ouvertes simultanement partageraient un `jti`."""
    moment = now()
    _, first, _ = issue(at=moment)
    _, second, _ = issue(at=moment)

    assert first != second


# ===========================================================================
# Piege n° 4 : confusion de type
# ===========================================================================


def test_a_refresh_token_is_refused_where_an_access_token_is_expected(settings):
    """
    Le plus grave des quatre pieges, et le moins connu.

    Sans ce controle, le jeton a longue duree de vie — 7 jours — devient
    utilisable comme jeton d acces. La rotation entiere est contournee : plus
    besoin de rafraichir, donc plus jamais de detection de reutilisation.
    """
    refresh, _, _ = issue(TokenType.REFRESH, lifetime=REFRESH_LIFETIME, family=str(uuid.uuid4()))

    with pytest.raises(TokenInvalidError):
        decode_token(refresh, expected_type=TokenType.ACCESS)


def test_an_access_token_is_refused_where_a_refresh_token_is_expected(settings):
    """Le sens inverse compte aussi : il ferait tourner une famille sur un access."""
    access, _, _ = issue(TokenType.ACCESS)

    with pytest.raises(TokenInvalidError):
        decode_token(access, expected_type=TokenType.REFRESH)


# ===========================================================================
# Piege n° 1 : alg none
# ===========================================================================


def test_a_token_declaring_no_signature_is_refused(settings):
    """
    `alg: none` est l attaque JWT de manuel : l attaquant reecrit la charge
    utile et supprime la signature. Elle ne fonctionne que si le decodeur
    accepte l algorithme annonce par le JETON plutot que celui qu il attend.
    """
    forged = jwt.encode(
        {
            "sub": str(SUBJECT),
            "token_type": "access",
            "role": "ADMIN",
            "jti": str(uuid.uuid4()),
            "iat": int(now().timestamp()),
            "exp": int((now() + ACCESS_LIFETIME).timestamp()),
            "iss": settings.JWT_ISSUER,
        },
        "",
        algorithm="none",
    )

    with pytest.raises(TokenInvalidError):
        decode_token(forged, expected_type=TokenType.ACCESS)


# ===========================================================================
# Piege n° 2 : confusion d algorithme
# ===========================================================================


def test_a_token_signed_with_another_algorithm_is_refused(settings):
    """
    Meme cle, algorithme different : refuse.

    C est la forme testable sans RSA de la confusion d algorithme. La variante
    celebre — un jeton HS256 signe avec la cle PUBLIQUE RSA du serveur — repose
    sur le meme defaut : accepter l algorithme que le jeton declare. La liste
    explicite du decodeur ferme les deux d un coup.
    """
    forged = jwt.encode(
        {
            "sub": str(SUBJECT),
            "token_type": "access",
            "jti": str(uuid.uuid4()),
            "iat": int(now().timestamp()),
            "exp": int((now() + ACCESS_LIFETIME).timestamp()),
            "iss": settings.JWT_ISSUER,
        },
        # Cle allongee uniquement pour eviter l avertissement de PyJWT sur la
        # longueur minimale en SHA-512 : le refus intervient sur l ALGORITHME,
        # avant toute verification de signature. Le test prouve donc bien ce
        # qu il annonce.
        (settings.JWT_SIGNING_KEY * 4)[:64],
        algorithm="HS512",
    )

    with pytest.raises(TokenInvalidError):
        decode_token(forged, expected_type=TokenType.ACCESS)


def test_a_token_signed_with_the_django_secret_key_is_refused(settings):
    """
    Les deux secrets sont distincts, et ce test le prouve.

    Si la cle de signature etait `SECRET_KEY`, une fuite de celle-ci — un
    reglage verse dans un ticket, une page d erreur bavarde — permettrait de
    forger un jeton d administrateur. Deux secrets, deux rayons d explosion.
    """
    forged = jwt.encode(
        {
            "sub": str(SUBJECT),
            "token_type": "access",
            "role": "ADMIN",
            "jti": str(uuid.uuid4()),
            "iat": int(now().timestamp()),
            "exp": int((now() + ACCESS_LIFETIME).timestamp()),
            "iss": settings.JWT_ISSUER,
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    assert settings.JWT_SIGNING_KEY != settings.SECRET_KEY
    with pytest.raises(TokenInvalidError):
        decode_token(forged, expected_type=TokenType.ACCESS)


def test_a_tampered_payload_breaks_the_signature(settings):
    """Elever son propre role en reecrivant la charge utile : refuse."""
    token, _, _ = issue(role="FAN")
    header, payload, signature = token.split(".")
    escalated = jwt.encode({"role": "ADMIN"}, "", algorithm="none").split(".")[1]

    with pytest.raises(TokenInvalidError):
        decode_token(f"{header}.{escalated}.{signature}", expected_type=TokenType.ACCESS)


# ===========================================================================
# Piege n° 3 : expiration
# ===========================================================================


def test_an_expired_token_is_reported_as_expired_not_as_invalid(settings):
    """
    Le seul motif distingue des autres.

    Le client DOIT savoir qu il faut rafraichir plutot que se reconnecter, et
    l information ne sert a rien a un attaquant : un jeton expire est un jeton
    qu il possede deja.
    """
    settings.JWT_LEEWAY_SECONDS = 0
    long_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
    token, _, _ = issue(at=long_ago)

    with pytest.raises(TokenExpiredError):
        decode_token(token, expected_type=TokenType.ACCESS)


def test_the_clock_tolerance_is_bounded_and_explicit(settings):
    """
    Une tolerance existe — les horloges de deux machines derivent — mais elle
    est LUE DANS LES REGLAGES et bornee. Une tolerance genereuse posee « au cas
    ou » rallonge la duree de vie reelle de chaque jeton, revocation comprise.
    """
    settings.JWT_LEEWAY_SECONDS = 60
    just_expired = (
        datetime.datetime.now(datetime.timezone.utc) - ACCESS_LIFETIME - datetime.timedelta(seconds=5)
    )
    token, _, _ = issue(at=just_expired)

    assert decode_token(token, expected_type=TokenType.ACCESS)["sub"] == str(SUBJECT)

    settings.JWT_LEEWAY_SECONDS = 0
    with pytest.raises(TokenExpiredError):
        decode_token(token, expected_type=TokenType.ACCESS)


# ===========================================================================
# Claims obligatoires et emetteur
# ===========================================================================


@pytest.mark.parametrize("missing", REQUIRED_CLAIMS)
def test_a_token_missing_any_required_claim_is_refused(settings, missing):
    """
    Sans `exp` le jeton serait eternel ; sans `jti`, irrevocable ; sans
    `token_type`, interchangeable. PyJWT ne verifie la PRESENCE d un claim que
    si on la demande explicitement — d ou la liste `require`.
    """
    payload = {
        "sub": str(SUBJECT),
        "token_type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now().timestamp()),
        "exp": int((datetime.datetime.now(datetime.timezone.utc) + ACCESS_LIFETIME).timestamp()),
        "iss": settings.JWT_ISSUER,
    }
    del payload[missing]
    forged = jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises((TokenInvalidError, TokenExpiredError)):
        decode_token(forged, expected_type=TokenType.ACCESS)


def test_a_token_from_another_issuer_is_refused(settings):
    """
    Verifier `iss` ne sert a rien aujourd hui — un seul service emet. Cela
    servira le jour ou un second emetteur existera, et ce jour-la personne ne
    pensera a ajouter le controle : on l ecrit maintenant, ou jamais.
    """
    forged = jwt.encode(
        {
            "sub": str(SUBJECT),
            "token_type": "access",
            "jti": str(uuid.uuid4()),
            "iat": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
            "exp": int((datetime.datetime.now(datetime.timezone.utc) + ACCESS_LIFETIME).timestamp()),
            "iss": "un-autre-service",
        },
        settings.JWT_SIGNING_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(TokenInvalidError):
        decode_token(forged, expected_type=TokenType.ACCESS)


def test_garbage_is_refused_without_raising_anything_else(settings):
    """Une entree qui n a rien d un jeton ne doit pas produire une 500."""
    for rubbish in ("", "abc", "a.b.c", "Bearer x.y.z", "." * 40):
        with pytest.raises(TokenInvalidError):
            decode_token(rubbish, expected_type=TokenType.ACCESS)


def test_no_secret_ever_reaches_the_payload(settings):
    """
    Une charge utile JWT est SIGNEE, pas chiffree : n importe qui la lit.

    Ce test fige la liste des claims emis. Y ajouter un jour l adresse, le
    telephone ou pire fera echouer ici — c est le but, la question devra etre
    posee explicitement.
    """
    token, _, _ = issue(role="FAN", did="d-1", sid="s-1", auth_level=1)
    claims = decode_token(token, expected_type=TokenType.ACCESS)

    assert set(claims) == {
        "sub",
        "role",
        "did",
        "sid",
        "auth_level",
        "token_type",
        "jti",
        "iat",
        "exp",
        "iss",
    }
    assert settings.JWT_SIGNING_KEY not in token.split(".")[1]
