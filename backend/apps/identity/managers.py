"""
`UserManager` — low-level user construction.

This manager is NOT the registration service. `RegistrationService` owns
business rules such as age validation, over-posting protection, explicit terms
consent, and enumeration protections. The manager only constructs a valid user
object.

It still rejects structural omissions: `email`, `date_of_birth`, and
`terms_accepted_at` are required so no code path, including tests, can create
an incomplete user and make those invariants appear optional.
"""

from typing import Any

from django.contrib.auth.models import BaseUserManager
from django.utils import timezone

from .constants import DEFAULT_ROLE, ROLE_ADMIN


class UserManager(BaseUserManager):
    """Manager for `identity.User`, whose login identifier is email."""

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
        Create a user. `normalize_email` lowercases the domain portion, while
        the database `citext` column also enforces case-insensitive uniqueness.
        """
        if not email:
            raise ValueError("L'email est obligatoire : c'est l'identifiant de connexion.")
        if date_of_birth is None:
            raise ValueError("La date de naissance est obligatoire (RM-13, âge >= 16 ans).")
        if terms_accepted_at is None:
            raise ValueError("L'horodatage d'acceptation des CGU est obligatoire.")

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
        Create an administrator account for `manage.py createsuperuser`.

        `terms_accepted_at` is stamped at creation because an operator-created
        CLI account does not pass through the public registration consent form.
        This path never applies to public registration.
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
        Perform a case-insensitive email lookup.

        No `LOWER()` is necessary because the column uses `citext`, so the
        database comparison is case-insensitive and can still use the unique
        index.
        """
        return self.get(email=email)

    def get_by_natural_key(self, username: str | None) -> Any:
        # BaseUserManager requires the `str | None` signature. Delegate directly
        # to get() so a null email produces the model's DoesNotExist exception,
        # which Django authentication backends expect.
        return self.get(email=username)
