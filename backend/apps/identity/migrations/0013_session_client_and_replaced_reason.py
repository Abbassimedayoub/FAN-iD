from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0012_user_temporary_password_expires_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="client",
            field=models.CharField(
                blank=True,
                choices=[("web", "web"), ("mobile", "mobile")],
                help_text=(
                    "Canal ayant ouvert la session. Null uniquement pour les sessions "
                    "historiques ou les appels internes anterieurs a ce champ."
                ),
                max_length=10,
                null=True,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="session",
            name="ck_session_revoked_reason_valid",
        ),
        migrations.AddConstraint(
            model_name="session",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(revoked_reason__isnull=True)
                    | models.Q(
                        revoked_reason__in=[
                            "LOGOUT",
                            "ROTATION_REUSE",
                            "PASSWORD_CHANGE",
                            "ADMIN",
                            "DEVICE_RESET",
                            "SCANNER_REMOVED",
                            "REPLACED",
                        ]
                    )
                ),
                name="ck_session_revoked_reason_valid",
            ),
        ),
    ]
