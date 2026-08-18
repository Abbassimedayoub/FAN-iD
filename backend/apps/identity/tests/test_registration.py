"""
`POST /api/v1/auth/register` — premier point de terminaison metier du projet.

Ce fichier teste trois choses distinctes, et il vaut la peine de les separer :
le CONTRAT HTTP (codes, corps, en-tetes), les REGLES METIER (age, consentement,
unicite) et les INVARIANTS TRANSVERSAUX (pas de sur-postage, pas de secret dans
les journaux ni dans l evenement, evenement emis dans la transaction).
"""

from __future__ import annotations

import datetime

import pytest
from django.contrib.auth.hashers import get_hasher, identify_hasher
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.outbox.models import OutboxEvent
from apps.identity.constants import MINIMUM_AGE_YEARS, ROLE_FAN
from apps.identity.events import USER_REGISTERED
from apps.identity.models import User
from apps.identity.services.registration import age_in_years

URL = "/api/v1/auth/register"
STRONG_PASSWORD = "Chataigne-Orageuse-2026"


@pytest.fixture(autouse=True)
def isolated_throttle_cache(settings):
    """
    Compteur de limitation de debit local au test.

    Sans cela, le compteur vit dans le Redis partage : les huit processus de
    `pytest -n auto` s incrementeraient mutuellement — toutes les requetes
    d inscription des tests viennent de la meme adresse 127.0.0.1 — et le
    premier test malchanceux recevrait un 429. C est la recette d un test
    instable qui echoue une fois sur cinq et que l on finit par desactiver.
    """
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "throttle-register-tests",
        }
    }
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def payload(**overrides):
    body = {
        "email": "supporter@example.test",
        "password": STRONG_PASSWORD,
        "first_name": "Ines",
        "last_name": "Bouzid",
        "date_of_birth": "1996-05-04",
        "terms_accepted": True,
    }
    body.update(overrides)
    return body


def birthdate_for_age(age: int, *, extra_days: int = 0) -> str:
    """
    Date de naissance donnant exactement `age` ans aujourd hui.

    Le repli sur le 1er mars n est pas de la coquetterie : un 29 fevrier,
    `date(annee - 16, 2, 29)` leve `ValueError` si l annee cible n est pas
    bissextile. Une suite de tests qui echoue un jour sur 1461 est pire qu une
    suite qui echoue toujours — on met des mois a la croire.
    """
    today = timezone.localdate()
    month, day = (3, 1) if (today.month, today.day) == (2, 29) else (today.month, today.day)
    born = datetime.date(today.year - age, month, day) + datetime.timedelta(days=extra_days)
    return born.isoformat()


# ===========================================================================
# Contrat HTTP
# ===========================================================================


@pytest.mark.django_db
def test_a_valid_registration_returns_201_and_the_public_representation(client, roles):
    response = client.post(URL, payload(), format="json")

    assert response.status_code == 201, response.data
    body = response.data
    assert set(body) == {"id", "email", "first_name", "last_name", "role", "created_at"}
    assert body["email"] == "supporter@example.test"
    assert body["first_name"] == "Ines"
    assert body["role"] == ROLE_FAN


@pytest.mark.django_db
def test_the_response_never_echoes_the_password(client, roles):
    """
    Un mot de passe renvoye finirait dans les journaux du client, le cache du
    navigateur et les outils de supervision front. La verification porte sur le
    CORPS BRUT, pas sur les cles : un serialiseur imbrique pourrait le glisser
    ailleurs que sous la cle `password`.
    """
    response = client.post(URL, payload(), format="json")

    assert response.status_code == 201
    assert STRONG_PASSWORD not in response.content.decode()


@pytest.mark.django_db
def test_the_stored_password_is_hashed_by_the_configured_hasher(client, roles):
    """
    Le mot de passe stocke est illisible et verifiable — rien de plus.

    Ce test n exige PAS Argon2 : l environnement de test a le droit d installer
    un algorithme rapide, sans quoi chaque creation d utilisateur coute 64 Mio
    et quelques centaines de millisecondes. Coder « argon2 » en dur ici
    reviendrait a tester la configuration de test, pas le comportement du code.

    Que la PRODUCTION utilise bien Argon2id est une propriete des reglages, pas
    du chemin d execution : c est le test suivant qui s en charge, sur
    `config.settings.base` directement, hors de portee de toute surcharge.
    """
    client.post(URL, payload(), format="json")
    user = User.objects.get(email="supporter@example.test")

    assert user.password != STRONG_PASSWORD
    assert STRONG_PASSWORD not in user.password
    assert identify_hasher(user.password).algorithm == get_hasher("default").algorithm
    assert user.check_password(STRONG_PASSWORD)


def test_production_settings_hash_passwords_with_argon2id():
    """
    Lu sur `config.settings.base`, jamais sur les reglages actifs.

    Une surcharge de test — legitime pour la vitesse — masquerait la regression
    qui compte : quelqu un qui affaiblirait le hachage de PRODUCTION. On lit
    donc la source, pas l execution.
    """
    from config.settings import base as base_settings

    assert base_settings.PASSWORD_HASHERS[0] == "apps.identity.hashers.FanIdArgon2PasswordHasher"


# ===========================================================================
# Regles metier
# ===========================================================================


@pytest.mark.django_db
def test_someone_below_the_minimum_age_is_refused_with_an_actionable_code(client, roles):
    too_young = birthdate_for_age(MINIMUM_AGE_YEARS, extra_days=1)
    response = client.post(URL, payload(date_of_birth=too_young), format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "UNDERAGE"
    assert response.data["error"]["details"] == {"minimum_age_years": MINIMUM_AGE_YEARS}
    assert not User.objects.exists()


@pytest.mark.django_db
def test_exactly_the_minimum_age_is_accepted(client, roles):
    """La borne est INCLUSIVE : le jour de ses 16 ans, l inscription passe."""
    response = client.post(URL, payload(date_of_birth=birthdate_for_age(MINIMUM_AGE_YEARS)), format="json")

    assert response.status_code == 201, response.data


@pytest.mark.django_db
def test_refusing_the_terms_is_a_named_business_error_not_a_field_error(client, roles):
    """
    Le consentement est une regle METIER, pas une contrainte de forme.

    Le serialiseur accepte donc `false` — c est un booleen valide — et le
    service tranche. Ainsi la regle s applique aussi a un appelant qui n
    utiliserait pas ce serialiseur : commande d administration, reprise de
    donnees, second point de terminaison.
    """
    response = client.post(URL, payload(terms_accepted=False), format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "TERMS_NOT_ACCEPTED"
    assert not User.objects.exists()


@pytest.mark.django_db
def test_the_consent_timestamp_comes_from_the_server_not_from_the_client(client, roles):
    """
    Une preuve de consentement fournie par la partie qu elle engage ne prouve
    rien. Le champ envoye par le client est ignore — il n existe meme pas dans
    le contrat d entree.
    """
    before = timezone.now()
    client.post(URL, payload(terms_accepted_at="1999-01-01T00:00:00Z"), format="json")

    user = User.objects.get(email="supporter@example.test")
    assert user.terms_accepted_at >= before


@pytest.mark.django_db
def test_the_same_address_in_another_case_is_refused_as_a_duplicate(client, roles):
    """L unicité est insensible a la casse grace au type `citext` (S1-A.1a)."""
    assert client.post(URL, payload(), format="json").status_code == 201

    response = client.post(URL, payload(email="Supporter@Example.TEST"), format="json")

    # 400 et non 409 : le code d erreur est un contrat publie (plan §3.4), et
    # les clients React et Flutter seront ecrits contre lui. Mon avis — 409
    # decrit mieux un conflit de ressource — arrive apres la publication.
    assert response.status_code == 400
    assert response.data["error"]["code"] == "EMAIL_ALREADY_EXISTS"
    assert User.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("weak", "why"),
    [
        ("Ab-12", "moins de 10 caracteres"),
        ("1234567890", "entierement numerique"),
    ],
)
def test_a_weak_password_is_refused_and_never_appears_in_the_error(client, roles, weak, why):
    """
    Deux validateurs deterministes plutot qu un mot de passe « courant ».

    S appuyer sur `CommonPasswordValidator` rendrait le test dependant du
    contenu exact de la liste embarquee par Django, qui evolue d une version a
    l autre : le test passerait au vert le jour ou le mot choisi en sortirait,
    sans que personne ne s en apercoive.

    Le second point compte autant : le mot de passe refuse ne doit apparaitre
    NULLE PART dans la reponse. Un message d erreur qui cite la valeur rejetee
    la depose dans les journaux d acces, les traces et l historique du client.
    """
    response = client.post(URL, payload(password=weak), format="json")

    assert response.status_code == 400, why
    assert weak not in response.content.decode()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_a_password_too_similar_to_the_email_is_refused(client, roles):
    """
    Le validateur de similarite n a d interet qu a l inscription — c est le seul
    moment ou l on connait l adresse ET le mot de passe en clair. Le serialiseur
    lui fournit donc un utilisateur non persiste comme contexte.
    """
    response = client.post(
        URL, payload(email="chataigne.orageuse@example.test", password="chataigne.orageuse"), format="json"
    )

    assert response.status_code == 400
    assert not User.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_an_empty_name_is_refused(client, roles, field):
    """
    Nom et prenom obligatoires (AB-06).

    Un billet nominatif controle a l entree a besoin d un nom : la donnee a un
    usage identifie, ce qui la rend conforme a la minimisation RGPD. Le cas
    « uniquement des espaces » compte autant que la chaine vide — DRF rogne les
    blancs par defaut sur `CharField`, ce test fige ce comportement.
    """
    assert client.post(URL, payload(**{field: ""}), format="json").status_code == 400
    assert client.post(URL, payload(**{field: "   "}), format="json").status_code == 400
    assert not User.objects.exists()


@pytest.mark.django_db
def test_a_birth_date_in_the_future_is_a_form_error_not_an_age_refusal(client, roles):
    tomorrow = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
    response = client.post(URL, payload(date_of_birth=tomorrow), format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


# ===========================================================================
# Invariants transversaux
# ===========================================================================


@pytest.mark.django_db
def test_over_posting_privileged_fields_has_no_effect(client, roles):
    """
    L escalade la plus banale : poster `role` ou `is_staff` dans le corps.

    Ils ne sont pas filtres — ils n existent ni dans le serialiseur, ni dans
    `RegistrationCommand`. Un filtre s oublie lors de l ajout d un champ ; une
    structure fermee, non.
    """
    response = client.post(
        URL,
        payload(
            role=str(roles["ADMIN"].id),
            is_staff=True,
            is_superuser=True,
            anonymized_at="2020-01-01T00:00:00Z",
        ),
        format="json",
    )

    assert response.status_code == 201, response.data
    user = User.objects.get(email="supporter@example.test")
    assert user.role.name == ROLE_FAN
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.anonymized_at is None


@pytest.mark.django_db
def test_registration_publishes_exactly_one_event_with_no_personal_data(client, roles):
    client.post(URL, payload(), format="json")

    user = User.objects.get(email="supporter@example.test")
    events = list(OutboxEvent.objects.filter(event_type=USER_REGISTERED))

    assert len(events) == 1
    event = events[0]
    assert str(event.aggregate_id) == str(user.pk)
    assert event.payload == {"role": ROLE_FAN}

    # Ni adresse ni mot de passe dans la charge utile : l `outbox` est conservee
    # 30 jours et relayee vers un courtier — y recopier une donnee personnelle la
    # duplique hors du perimetre que l anonymisation RGPD sait atteindre.
    serialized = str(event.payload)
    assert "example.test" not in serialized
    assert STRONG_PASSWORD not in serialized


@pytest.mark.django_db
def test_a_refused_registration_publishes_no_event(client, roles):
    """
    L evenement et la creation partagent une transaction (invariant I-5).

    Ce test verifie le sens qui compte : si le compte n existe pas, l evenement
    ne doit pas exister non plus. Un courriel de bienvenue pour un compte
    inexistant serait le symptome typique d une publication hors transaction.
    """
    client.post(URL, payload(terms_accepted=False), format="json")

    assert not User.objects.exists()
    assert not OutboxEvent.objects.filter(event_type=USER_REGISTERED).exists()


@pytest.mark.django_db
def test_the_endpoint_throttles_repeated_attempts(client, roles, monkeypatch):
    """
    La reponse 409 sur adresse existante permet d enumerer les comptes. On ne
    supprime pas cette divulgation — on la rend couteuse. Ce test prouve que le
    seuil dedie s applique bien a CE point de terminaison, et pas le seuil
    anonyme generique de 60 par minute.
    """
    # `override_settings` serait SANS EFFET ici : DRF fige
    # `SimpleRateThrottle.THROTTLE_RATES` a l import du module, en capturant
    # l objet dictionnaire. Recharger les reglages remplace le dictionnaire de
    # `api_settings` mais la classe pointe toujours sur l ancien. Le test
    # passerait donc au vert en ne testant rien. On patche donc la classe.
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"register": "2/hour"})

    assert client.post(URL, payload(email="a@example.test"), format="json").status_code == 201
    assert client.post(URL, payload(email="b@example.test"), format="json").status_code == 201
    blocked = client.post(URL, payload(email="c@example.test"), format="json")

    assert blocked.status_code == 429
    assert blocked.data["error"]["code"] == "RATE_LIMIT_EXCEEDED"


# ===========================================================================
# Calcul de l age
# ===========================================================================


@pytest.mark.parametrize(
    ("birth", "today", "expected"),
    [
        ((2010, 1, 1), (2026, 1, 1), 16),  # jour anniversaire : inclusif
        ((2010, 1, 2), (2026, 1, 1), 15),  # la veille : pas encore
        ((2010, 12, 31), (2026, 1, 1), 15),
        ((2008, 2, 29), (2026, 2, 28), 17),  # ne un 29 fevrier, annee non bissextile
        ((2008, 2, 29), (2026, 3, 1), 18),
        ((2000, 6, 15), (2026, 6, 14), 25),
    ],
)
def test_age_is_computed_by_calendar_not_by_dividing_days(birth, today, expected):
    """
    `(today - birth).days // 365` derive d un jour tous les quatre ans, et fait
    basculer un utilisateur du bon cote de la limite un jour trop tot. Les deux
    cas du 29 fevrier sont la pour figer ce comportement : le natif attend le
    1er mars, jamais l inverse.
    """
    assert age_in_years(datetime.date(*birth), datetime.date(*today)) == expected
