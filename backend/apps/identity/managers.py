"""
`UserManager` — construction bas niveau d'un utilisateur (plan S1 §2.5).

Ce manager n'est PAS le service d'inscription. `RegistrationService` (lot S1-A.3)
porte les règles métier : validation d'âge avec message exploitable, refus du
sur-postage de `role`/`is_staff`/`is_active`, consentement CGU explicite,
anti-énumération. Le manager ne fait que construire l'objet correctement.

Il refuse néanmoins les oublis structurels — `email`, `date_of_birth` et
`terms_accepted_at` sont obligatoires — pour qu'aucun chemin de code, test
compris, ne puisse créer un utilisateur incomplet et faire croire que la règle
est optionnelle.
"""

from typing import Any

from django.contrib.auth.models import BaseUserManager
from django.utils import timezone

from .constants import DEFAULT_ROLE, ROLE_ADMIN


class UserManager(BaseUserManager):
    """Manager de `identity.User`, dont l'identifiant de connexion est l'email."""

    use_in_migrations = False

    def _resolve_role(self, role: Any, fallback_name: str) -> Any:
        if role is not None:
            return role
        from .models import Role

        return Role.objects.get(name=fallback_name)

    def create_user(
        self,
        email: str,
        password: str | None = None,
        *,
        date_of_birth: Any,
        terms_accepted_at: Any,
        role: Any = None,
        **extra_fields: Any,
    ) -> Any:
        """
        Crée un utilisateur. `email` est normalisé (partie domaine en minuscules)
        par `normalize_email`; l'unicité insensible à la casse est en outre
        garantie par le type `citext` en base (voir `fields.py`).
        """
        if not email:
            raise ValueError("L'email est obligatoire : c'est l'identifiant de connexion.")
        if date_of_birth is None:
            raise ValueError("La date de naissance est obligatoire (RM-13, âge >= 16 ans).")
        if terms_accepted_at is None:
            raise ValueError("L'horodatage d'acceptation des CGU est obligatoire (RGPD §15.4).")

        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        user: Any = self.model(
            email=self.normalize_email(email),
            date_of_birth=date_of_birth,
            terms_accepted_at=terms_accepted_at,
            role=self._resolve_role(role, DEFAULT_ROLE),
            **extra_fields,
        )
        user.set_password(password)
        user.full_clean(exclude=["password"], validate_unique=False)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        *,
        date_of_birth: Any,
        **extra_fields: Any,
    ) -> Any:
        """
        Crée un administrateur (`manage.py createsuperuser`).

        `terms_accepted_at` est horodaté à l'instant de la création : un compte
        créé en ligne de commande par un opérateur ne passe pas par un formulaire
        de consentement. C'est un choix assumé, tracé ici, et qui ne concerne
        jamais un compte issu de l'inscription publique.
        """
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return self.create_user(
            email,
            password,
            date_of_birth=date_of_birth,
            terms_accepted_at=timezone.now(),
            role=self._resolve_role(extra_fields.pop("role", None), ROLE_ADMIN),
            **extra_fields,
        )

    def get_by_email_ci(self, email: str) -> Any:
        """
        Recherche insensible à la casse.

        Aucun `LOWER()` n'est nécessaire : la colonne est de type `citext`, la
        comparaison est donc insensible à la casse au niveau du SGBD et
        l'index unique reste utilisable (plan S1 §2.5).
        """
        return self.get(email=email)

    def get_by_natural_key(self, username: str | None) -> Any:
        # Signature imposee par BaseUserManager (str | None). On delegue a get()
        # plutot qu a get_by_email_ci() : un email nul produit alors le DoesNotExist
        # du modele, que les backends d authentification de Django attendent.
        return self.get(email=username)
