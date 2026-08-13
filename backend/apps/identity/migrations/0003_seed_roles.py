"""
Seed du référentiel des rôles (plan S1 §3.1 : « migration de données idempotente,
avec fonction inverse »).
 
Idempotence : `update_or_create` sur un identifiant FIXE (voir
`apps/identity/constants.py`). Rejouer la migration ne crée pas de doublon et ne
casse pas les clés étrangères existantes.
 
Réversibilité : la fonction inverse ne supprime QUE les rôles encore inutilisés.
Supprimer un rôle référencé par un utilisateur échouerait de toute façon sur la
contrainte `PROTECT` — autant le dire explicitement plutôt que de laisser
l'erreur remonter du SGBD.
"""
from django.db import migrations
 
# Dupliqué depuis apps/identity/constants.py à dessein : une migration doit
# rester figée dans le temps. Si les constantes évoluent, cette migration
# continue de décrire l'état du schéma tel qu'il était à sa date.
ROLES = [
    ("80d63969-f419-5bd6-b682-653e21e74a65", "FAN"),
    ("ea173779-0ab3-56b8-9924-23915ef7fc29", "ORGANIZER"),
    ("91e56bcb-d23e-5169-a1f3-655e1e44f277", "SCANNER"),
    ("58d71579-cab7-576e-b233-27c1c424b8bd", "ADMIN"),
]
 
#: Descriptif uniquement (ADR-02) : la source de vérité est le PolicyEngine.
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
