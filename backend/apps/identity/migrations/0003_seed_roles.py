"""
Seed the role reference table with deterministic identifiers.

Idempotency comes from `update_or_create` using fixed UUIDs. Replaying the
migration cannot create duplicate roles or break existing foreign keys.

The reverse function deletes only roles that are still unused. Referenced roles
are intentionally preserved.
"""
from django.db import migrations

# Duplicated from apps/identity/constants.py intentionally: migrations are
# historical artifacts and must remain frozen even if runtime constants evolve.
ROLES = [
    ("80d63969-f419-5bd6-b682-653e21e74a65", "FAN"),
    ("ea173779-0ab3-56b8-9924-23915ef7fc29", "ORGANIZER"),
    ("91e56bcb-d23e-5169-a1f3-655e1e44f277", "SCANNER"),
    ("58d71579-cab7-576e-b233-27c1c424b8bd", "ADMIN"),
]

#: Descriptive metadata only; runtime authorization comes from the code policy.
PERMISSIONS = {
    "FAN": {"description": "Achète, détient et transfère ses billets."},
    "ORGANIZER": {"description": "Crée et administre ses événements, une fois le compte approuvé."},
    "SCANNER": {"description": "Valide les billets des événements auxquels il est affecté."},
    "ADMIN": {"description": "Administre la plateforme et valide les organisateurs."},
}


def seed_roles(apps, schema_editor):
    Role = apps.get_model("identity", "Role")
    for role_id, name in ROLES:
        Role.objects.update_or_create(
            id=role_id,
            defaults={"name": name, "permissions": PERMISSIONS[name]},
        )


def unseed_roles(apps, schema_editor):
    Role = apps.get_model("identity", "Role")
    Role.objects.filter(id__in=[role_id for role_id, _ in ROLES], users__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0002_role_and_user_identity"),
    ]

    operations = [
        migrations.RunPython(seed_roles, unseed_roles),
    ]
