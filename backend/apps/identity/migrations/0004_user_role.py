"""
Attach `user.role` through a protected foreign key.

This migration is separate from the role seed so the referenced role rows
already exist when the column is added.

The temporary default is FAN and is removed immediately with
`preserve_default=False`. FAN is the least-privileged public registration
role. `PROTECT` prevents role deletion from cascading into user deletion.
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
