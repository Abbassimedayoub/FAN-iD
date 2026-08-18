"""
Rattachement de `user.role` (plan S1 §3.1 : `FK role_id ON DELETE PROTECT`).

Migration séparée du seed : ADR-S-08 interdit de mêler l'ajout d'une colonne et
le peuplement des données dont elle dépend. Les rôles existent donc déjà quand
cette migration s'exécute, et la valeur par défaut peut pointer un identifiant
réel.

`default` = FAN, immédiatement retiré (`preserve_default=False`). Le rôle FAN est
celui de l'inscription publique (master prompt §11) : c'est le défaut le moins
privilégié possible, jamais ADMIN.

`PROTECT` et non `CASCADE` : supprimer un rôle ne doit jamais supprimer en
cascade les utilisateurs qui le portent.
"""
import django.db.models.deletion
from django.db import migrations, models

ROLE_FAN_ID = "80d63969-f419-5bd6-b682-653e21e74a65"


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0003_seed_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.ForeignKey(
                default=ROLE_FAN_ID,
                help_text="V1 : un seul rôle par utilisateur (ADR-01).",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="identity.role",
            ),
            preserve_default=False,
        ),
    ]
