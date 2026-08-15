"""
Cycle de vie des jetons : emission, rotation, detection de reutilisation.

Le test qui compte est `test_two_concurrent_rotations...` : il lance deux vrais
threads sur une vraie base et prouve qu une seule rotation aboutit. Les autres
verifient les chemins nominaux et les refus ; celui-la verifie l invariant qui
n existe que sous concurrence, et qu aucune lecture de code ne garantit.
"""

from __future__ import annotations

import datetime
import threading
import uuid

import pytest
from django.db import connection
from django.utils import timezone

from apps.identity.constants import (
    SESSION_REVOKED_LOGOUT,
    SESSION_REVOKED_PASSWORD_CHANGE,
    SESSION_REVOKED_ROTATION_REUSE,
)
from apps.identity.models import Session, User
from apps.identity.services.tokens import TokenService
from apps.identity.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    TokenReuseDetectedError,
    TokenType,
    decode_token,
)


def make_user(roles, email="rotation@example.test") -> User:
    return User.objects.create_user(
        email=email,
        password="Chataigne-Orageuse-2026",
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1996, 5, 4),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


@pytest.fixture
def fan(db, roles) -> User:
    return make_user(roles)


# ===========================================================================
# Emission
# ===========================================================================


def test_issuing_a_pair_opens_a_session_row_aligned_with_the_tokens(fan):
    """
    Le `jti` du refresh et l identifiant de session doivent correspondre
    EXACTEMENT a ce qui est stocke : c est ce qui rend la rotation possible sans
    redecoder le jeton a chaque requete.
    """
    pair = TokenService.issue_pair(user=fan)

    session = Session.objects.get(pk=pair.session.pk)
    refresh_claims = decode_token(pair.refresh, expected_type=TokenType.REFRESH)
    access_claims = decode_token(pair.access, expected_type=TokenType.ACCESS)

    assert str(session.refresh_jti) == refresh_claims["jti"]
    assert access_claims["sid"] == str(session.pk)
    assert refresh_claims["family"] == str(session.family_id)
    assert session.expires_at == pair.refresh_expires_at
    assert session.revoked_at is None


def test_the_access_token_carries_the_role_so_authorization_costs_no_query(fan):
    """
    Corollaire assume de ce choix (plan §3.5) : un changement de role ne prend
    effet qu au rafraichissement suivant — 15 minutes au pire. C est le prix
    d une decision d autorisation a moins d une milliseconde.
    """
    pair = TokenService.issue_pair(user=fan)

    claims = decode_token(pair.access, expected_type=TokenType.ACCESS)

    assert claims["role"] == "FAN"
    assert claims["auth_level"] == 1
    # Aucun appareil lie : le claim existe et vaut `null`, il n est pas absent.
    # Une absence serait ambigue — oubli d emission ou absence d appareil ?
    assert claims["did"] is None


def test_the_refresh_token_never_carries_the_role_or_the_device(fan):
    """
    Le refresh ne sert qu a obtenir un access. Lui donner des droits en ferait
    un second jeton d acces a longue duree de vie.
    """
    claims = decode_token(TokenService.issue_pair(user=fan).refresh, expected_type=TokenType.REFRESH)

    assert set(claims) == {"family", "token_type", "sub", "jti", "iat", "exp", "iss"}


def test_two_logins_open_two_independent_families(fan):
    first = TokenService.issue_pair(user=fan)
    second = TokenService.issue_pair(user=fan)

    assert first.session.family_id != second.session.family_id
    assert Session.objects.filter(user=fan, revoked_at__isnull=True).count() == 2


# ===========================================================================
# Rotation
# ===========================================================================


def test_rotating_keeps_the_session_and_the_family_but_changes_the_token(fan):
    """
    Une rotation ne crée PAS de session : elle fait avancer la meme lignee.

    Créer une ligne par rotation ferait grossir la table d une ligne toutes les
    15 minutes et par utilisateur, et surtout rendrait la revocation de famille
    proportionnelle au nombre de rotations plutot que constante.
    """
    original = TokenService.issue_pair(user=fan)

    rotated = TokenService.rotate(original.refresh)

    assert rotated.session.pk == original.session.pk
    assert rotated.session.family_id == original.session.family_id
    assert rotated.refresh != original.refresh

    session = Session.objects.get(pk=original.session.pk)
    assert str(session.refresh_jti) == decode_token(rotated.refresh, expected_type=TokenType.REFRESH)["jti"]
    assert Session.objects.filter(user=fan).count() == 1


def test_an_access_token_cannot_be_rotated(fan):
    pair = TokenService.issue_pair(user=fan)

    with pytest.raises(TokenInvalidError):
        TokenService.rotate(pair.access)


def test_an_expired_refresh_is_reported_as_expired(fan, settings):
    settings.JWT_LEEWAY_SECONDS = 0
    long_ago = timezone.now() - datetime.timedelta(days=8)
    pair = TokenService.issue_pair(user=fan, now=long_ago)

    with pytest.raises(TokenExpiredError):
        TokenService.rotate(pair.refresh)


def test_a_refresh_from_a_revoked_session_is_invalid_not_a_reuse(fan):
    """
    Se deconnecter puis rejouer son ancien refresh n est PAS une reutilisation.

    Distinguer les deux compte : `TOKEN_REUSE_DETECTED` alimente une metrique
    dont toute valeur non nulle declenche une inspection. Y verser les rejeux
    apres deconnexion — frequents, benins — rendrait l alerte inutilisable.
    """
    pair = TokenService.issue_pair(user=fan)
    TokenService.revoke_session(pair.session, SESSION_REVOKED_LOGOUT)

    with pytest.raises(TokenInvalidError) as caught:
        TokenService.rotate(pair.refresh)
    assert not isinstance(caught.value, TokenReuseDetectedError)


# ===========================================================================
# Detection de reutilisation
# ===========================================================================


def test_replaying_a_rotated_refresh_revokes_the_whole_family(fan):
    """
    Le coeur du dispositif.

    On ne revoque pas le jeton rejoue : on revoque la FAMILLE, y compris le
    refresh legitime emis une seconde plus tot. Impossible de savoir lequel des
    deux porteurs est l attaquant — celui qui rejoue peut etre le voleur comme
    la victime. Deconnecter les deux est le seul choix sur.
    """
    original = TokenService.issue_pair(user=fan)
    rotated = TokenService.rotate(original.refresh)

    with pytest.raises(TokenReuseDetectedError):
        TokenService.rotate(original.refresh)

    session = Session.objects.get(pk=original.session.pk)
    assert session.revoked_at is not None
    assert session.revoked_reason == SESSION_REVOKED_ROTATION_REUSE

    # Le jeton honnete tombe aussi : c est le prix, et il est assume.
    with pytest.raises(TokenInvalidError):
        TokenService.rotate(rotated.refresh)


def test_a_reuse_in_one_family_leaves_the_other_sessions_alive(fan):
    """
    La revocation est bornee a la famille : un vol sur le telephone ne doit pas
    deconnecter l ordinateur portable. C est precisement ce que la blacklist
    globale de simplejwt ne savait pas faire, et la raison d etre de la table
    `session`.
    """
    compromised = TokenService.issue_pair(user=fan)
    untouched = TokenService.issue_pair(user=fan)
    TokenService.rotate(compromised.refresh)

    with pytest.raises(TokenReuseDetectedError):
        TokenService.rotate(compromised.refresh)

    assert Session.objects.get(pk=untouched.session.pk).revoked_at is None
    assert TokenService.rotate(untouched.refresh) is not None


def test_a_forged_family_claim_does_not_revoke_anything(fan):
    """
    La famille est lue dans le jeton, mais elle ne sert QU A confirmer une
    reutilisation — jamais a retrouver la session. La recherche se fait sur le
    `jti`, protege par un index unique. Un jeton signe portant une famille
    inconnue obtient donc un refus sec, sans effet de bord.
    """
    alive = TokenService.issue_pair(user=fan)
    orphan = TokenService.issue_pair(user=fan)
    Session.objects.filter(pk=orphan.session.pk).delete()

    with pytest.raises(TokenInvalidError):
        TokenService.rotate(orphan.refresh)

    assert Session.objects.get(pk=alive.session.pk).revoked_at is None


# ===========================================================================
# Revocation
# ===========================================================================


def test_changing_a_password_must_be_able_to_close_every_session(fan):
    """
    Un mot de passe change parce qu on le croit compromis ne sert a rien si les
    sessions ouvertes avec l ancien survivent.
    """
    first = TokenService.issue_pair(user=fan)
    second = TokenService.issue_pair(user=fan)

    closed = TokenService.revoke_all_for_user(fan, SESSION_REVOKED_PASSWORD_CHANGE)

    assert closed == 2
    for pair in (first, second):
        assert Session.objects.get(pk=pair.session.pk).revoked_reason == SESSION_REVOKED_PASSWORD_CHANGE
        with pytest.raises(TokenInvalidError):
            TokenService.rotate(pair.refresh)


def test_revoking_twice_reports_no_second_victim(fan):
    """
    Idempotence de la revocation : le second appel ne compte rien et n ecrase
    pas le motif d origine. Sans cela, une deconnexion apres une detection de
    vol effacerait `ROTATION_REUSE` des journaux d audit.
    """
    pair = TokenService.issue_pair(user=fan)
    TokenService.revoke_family(pair.session.family_id, SESSION_REVOKED_ROTATION_REUSE)

    assert TokenService.revoke_family(pair.session.family_id, SESSION_REVOKED_LOGOUT) == 0
    assert Session.objects.get(pk=pair.session.pk).revoked_reason == SESSION_REVOKED_ROTATION_REUSE


# ===========================================================================
# Concurrence reelle
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_rotations_never_produce_two_valid_pairs(roles):
    """
    Deux threads, une vraie base, un seul gagnant.

    Sans `SELECT ... FOR UPDATE`, les deux transactions liraient la meme ligne
    et ecriraient deux `jti` differents : **deux refresh valides pour une seule
    session**, ce qui supprime purement et simplement la detection de
    reutilisation. Aucune relecture de code ne prouve cela — il faut deux
    threads.

    Le perdant recoit `TOKEN_REUSE_DETECTED` et la famille tombe. C est le
    comportement voulu : deux rafraichissements legitimes concurrents sont
    indiscernables d un vol. La parade est cote client — serialiser les
    rafraichissements derriere un seul verrou en vol (plan, § React).
    """
    fan = make_user(roles, email="concurrence@example.test")
    pair = TokenService.issue_pair(user=fan)

    start = threading.Barrier(2)
    winners: list[object] = []
    losers: list[Exception] = []

    def rotate_once() -> None:
        start.wait(timeout=5)
        try:
            winners.append(TokenService.rotate(pair.refresh))
        except Exception as exc:  # on capture pour ASSERTER le type, pas pour ignorer
            losers.append(exc)
        finally:
            # Chaque thread ouvre sa propre connexion : la laisser ouverte
            # empecherait le demontage de la base en fin de test.
            connection.close()

    threads = [threading.Thread(target=rotate_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        assert not thread.is_alive(), "rotation bloquee : verrou non libere"

    # Le message porte les DEUX listes : quand les deux threads echouent pour
    # une raison commune — une requete refusee par le SGBD, par exemple — un
    # message qui n affiche que les gagnants dit « deux rotations ont abouti :
    # [] », c est-a-dire l inverse de ce qui s est produit.
    diagnostic = f"gagnants={winners!r} perdants={losers!r}"
    assert len(winners) == 1, diagnostic
    assert len(losers) == 1, diagnostic
    assert isinstance(losers[0], TokenReuseDetectedError), diagnostic

    session = Session.objects.get(pk=pair.session.pk)
    assert session.revoked_reason == SESSION_REVOKED_ROTATION_REUSE


@pytest.mark.django_db(transaction=True)
def test_a_family_identifier_is_never_reused_across_users(roles):
    """
    Garde-fou : deux comptes ne doivent jamais partager une famille, sinon la
    revocation de l un deconnecterait l autre.
    """
    first = make_user(roles, email="famille-1@example.test")
    second = make_user(roles, email="famille-2@example.test")

    families = {
        TokenService.issue_pair(user=first).session.family_id,
        TokenService.issue_pair(user=second).session.family_id,
    }

    assert len(families) == 2
    assert all(isinstance(family, uuid.UUID) for family in families)
