"""
Serialiseurs du contexte `identity`.

Repartition des responsabilites, tenue strictement :

- le SERIALISEUR valide des FORMES — type, longueur, format, presence ;
- le SERVICE porte les REGLES METIER — age minimum, consentement, unicite.

La tentation inverse est forte : tout mettre dans le serialiseur donne des
messages d erreur bien places, champ par champ. Mais une regle metier ecrite
dans un serialiseur ne s applique qu aux appels HTTP qui passent par CE
serialiseur. Une commande d administration, une reprise de donnees ou un second
point de terminaison la contourneraient sans un mot.
"""

from __future__ import annotations

import datetime
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .constants import CLIENT_MOBILE, CLIENT_WEB, DEVICE_PLATFORMS
from .models import User


class RegistrationSerializer(serializers.Serializer):
    """
    Corps de `POST /api/v1/auth/register`.

    `Serializer` et non `ModelSerializer`, deliberement. Un `ModelSerializer`
    part des champs du MODELE et l on retire ceux qu on ne veut pas : le jour ou
    quelqu un ajoute une colonne, elle devient exposee par defaut. Ici la liste
    est FERMEE — `role`, `is_staff`, `is_superuser`, `is_active`, `anonymized_at`
    ne sont pas « exclus », ils n existent tout simplement pas dans le contrat
    d entree. C est la meme logique que `RegistrationCommand` cote service : la
    protection contre le sur-postage est structurelle, pas defensive.
    """

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        max_length=128,
        trim_whitespace=False,
    )
    # Obligatoires (AB-06). Un billet nominatif controle a l entree a besoin
    # d un nom : la donnee a donc un usage identifie, ce qui la rend conforme a
    # la minimisation RGPD. `allow_blank=False` est le defaut de DRF, mais un
    # nom fait uniquement d espaces passerait sans `trim_whitespace` — actif par
    # defaut ici, contrairement au mot de passe.
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    date_of_birth = serializers.DateField()
    terms_accepted = serializers.BooleanField()
    phone = serializers.CharField(
        max_length=32,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate_date_of_birth(self, value: datetime.date) -> datetime.date:
        """
        Une date future est une faute de SAISIE, pas un refus metier.

        La distinction compte pour le message : « la date ne peut pas etre dans
        le futur » se corrige, « vous etes trop jeune » ne se corrige pas. Le
        controle de l age minimum, lui, reste au service.
        """
        if value > timezone.localdate():
            raise serializers.ValidationError("La date de naissance ne peut pas etre dans le futur.")
        return value

    def validate_password(self, value: str) -> str:
        """
        Applique les validateurs de `AUTH_PASSWORD_VALIDATORS`.

        L utilisateur non persiste passe en contexte pour que
        `UserAttributeSimilarityValidator` puisse comparer le mot de passe a
        l adresse fournie DANS CETTE MEME requete. Sans lui, ce validateur n a
        rien a comparer et ne sert a rien a l inscription — c est-a-dire au seul
        moment ou il est vraiment utile.

        `trim_whitespace=False` sur le champ : rogner les espaces d un mot de
        passe en modifie silencieusement la valeur, et l utilisateur ne pourrait
        plus se connecter avec ce qu il a tape.
        """
        # Seuls `username`, `first_name`, `last_name` et `email` sont lus par
        # `UserAttributeSimilarityValidator`. Passer `date_of_birth=None` ne
        # servait a rien et mentait au verificateur de types : le champ est un
        # `DateField` non nul.
        candidate = User(email=str(self.initial_data.get("email", "")))
        try:
            validate_password(value, user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class LoginSerializer(serializers.Serializer):
    """
    Corps de `POST /api/v1/auth/login`.

    **`client` est obligatoire, et ce n est pas de la bureaucratie.** Il decide
    du TRANSPORT du jeton de rafraichissement : cookie HttpOnly pour le web,
    corps de reponse pour le mobile. Les deux ne se cumulent jamais — un refresh
    present dans le corps est lisible en JavaScript, et le cookie HttpOnly ne
    protegerait alors plus rien.

    Deduire le client du `User-Agent` serait plus discret et beaucoup moins sur :
    cet en-tete se falsifie, change a chaque version de navigateur, et
    transformerait une decision de securite en heuristique.

    `client` n est pas une donnee de confiance et ne doit jamais influencer les
    autorisations. Il choisit uniquement le canal de transport du refresh.

    Un navigateur qui declare `mobile` peut donc degrader la protection de son
    propre refresh, mais ne doit obtenir aucun privilege supplementaire.

    `fingerprint` reste facultatif : un supporter sur navigateur n a pas
    d empreinte stable a fournir, et l inventer a partir de l IP ou du
    `User-Agent` serait instable et disproportionne (RGPD).
    """

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        max_length=128,
        trim_whitespace=False,
    )
    client = serializers.ChoiceField(choices=[CLIENT_WEB, CLIENT_MOBILE])
    fingerprint = serializers.CharField(
        max_length=64,
        required=False,
        allow_null=True,
    )
    platform = serializers.ChoiceField(
        choices=list(DEVICE_PLATFORMS),
        required=False,
        allow_null=True,
    )

    # `label` est le SEUL nom de champ de ce module qui percute un attribut de
    # `Field` : la classe de base possede deja `label`, l intitule affichable
    # d un champ, type `str | None`. Le stub voit donc une redefinition
    # incompatible la ou DRF fait simplement ce qu il fait pour tous les champs
    # declaratifs — remplacer l attribut de classe par la valeur validee sur
    # l instance. Le renommer casserait le contrat d API (le client envoie bien
    # `label`), d ou l exception locale plutot qu un contournement global.
    label = serializers.CharField(  # type: ignore[assignment]
        max_length=60,
        required=False,
        allow_blank=True,
        default="",
    )


class RefreshSerializer(serializers.Serializer):
    """
    Corps de `POST /api/v1/auth/refresh`.

    **`client` ne sert pas qu a formater la reponse : il designe la SOURCE de
    lecture du jeton.** `web` lit le cookie et IGNORE le corps ; `mobile` lit le
    corps et IGNORE le cookie. Une source non declaree reste non lue, meme
    lorsqu elle porte un jeton parfaitement valide — c est ce qui empeche le
    cumul des deux transports interdit au lot S1-A.6c.

    `refresh` n est donc utile qu au client mobile. Le rendre obligatoire
    casserait le client web, dont le jeton n est pas dans le corps ; sa presence
    reelle est verifiee par la vue, seule a savoir quelle source elle doit lire.

    `fingerprint` est exigee des que la session porte un appareil. C est le
    service qui tranche, pas le serialiseur : la reponse depend de l etat de la
    session, pas de la forme du corps.
    """

    client = serializers.ChoiceField(choices=[CLIENT_WEB, CLIENT_MOBILE])
    # `max_length` borne l entree AVANT le decodage. Un JWT du projet fait
    # quelques centaines d octets ; laisser le champ libre reviendrait a offrir
    # a chaque appel non authentifie une verification de signature sur un corps
    # de plusieurs mega-octets. `trim_whitespace=False` parce qu un jeton n a
    # pas d espaces a rogner, et qu en rogner masquerait un client fautif.
    refresh = serializers.CharField(max_length=4096, required=False, allow_blank=True, trim_whitespace=False)
    fingerprint = serializers.CharField(max_length=64, required=False, allow_blank=True, allow_null=True)


class DeviceSerializer(serializers.Serializer):
    """L appareil lie, tel que le client a besoin de le connaitre."""

    id = serializers.UUIDField(read_only=True)
    label = serializers.CharField(read_only=True)  # type: ignore[assignment]  # cf. LoginSerializer.label
    bound_at = serializers.DateTimeField(read_only=True)


class UserPublicSerializer(serializers.Serializer):
    """
    Representation renvoyee au client.

    Ferme lui aussi : on n expose ni `is_staff`, ni `is_superuser`, ni
    `last_login`, ni `date_joined`, ni surtout `password`. Le role est expose
    par son NOM et non par son identifiant — un client n a aucune raison de
    connaitre les cles primaires du referentiel, et le nom reste stable.
    """

    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    role = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)

    def get_role(self, obj: Any) -> str:
        return str(obj.role.name)


class PasswordChangeSerializer(serializers.Serializer):
    """
    Corps de `POST /api/v1/auth/password/change`.

    Repartition habituelle : le serialiseur valide la FORME du nouveau mot de
    passe — longueur, robustesse, similarite avec le compte — et le SERVICE
    porte les regles metier : le mot de passe actuel est-il le bon, le nouveau
    differe-t-il de l ancien.

    L utilisateur reel passe en contexte, pas un candidat reconstruit comme a
    l inscription : ici il existe deja, donc `UserAttributeSimilarityValidator`
    peut comparer le nouveau mot de passe a l adresse ET au nom du compte. Sans
    ce passage, ce validateur n aurait rien a comparer et ne servirait a rien.

    `trim_whitespace=False` sur les deux champs : rogner les espaces d un mot de
    passe en modifie silencieusement la valeur.
    """

    current_password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)

    def validate_new_password(self, value: str) -> str:
        """Applique `AUTH_PASSWORD_VALIDATORS` contre l utilisateur reel."""
        user = getattr(self.context.get("request"), "user", None)
        if not getattr(user, "is_authenticated", False):
            user = None
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value
