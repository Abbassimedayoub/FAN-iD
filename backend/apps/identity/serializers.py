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
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    # Obligatoires (AB-06). Un billet nominatif controle a l entree a besoin
    # d un nom : la donnee a donc un usage identifie, ce qui la rend conforme a
    # la minimisation RGPD. `allow_blank=False` est le defaut de DRF, mais un
    # nom fait uniquement d espaces passerait sans `trim_whitespace` — actif par
    # defaut ici, contrairement au mot de passe.
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    date_of_birth = serializers.DateField()
    terms_accepted = serializers.BooleanField()
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, allow_null=True)

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
