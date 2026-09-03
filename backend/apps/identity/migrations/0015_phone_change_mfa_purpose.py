from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "identity",
            "0014_alter_session_revoked_reason",
        ),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="mfachallenge",
            name="ck_mfa_purpose_valid",
        ),
        migrations.AlterField(
            model_name="mfachallenge",
            name="purpose",
            field=models.CharField(
                choices=[
                    (
                        "DEVICE_RESET",
                        "DEVICE_RESET",
                    ),
                    (
                        "STEP_UP",
                        "STEP_UP",
                    ),
                    (
                        "EMAIL_CHANGE",
                        "EMAIL_CHANGE",
                    ),
                    (
                        "PHONE_CHANGE",
                        "PHONE_CHANGE",
                    ),
                    (
                        "PASSWORD_RESET",
                        "PASSWORD_RESET",
                    ),
                ],
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="mfachallenge",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    purpose__in=[
                        "DEVICE_RESET",
                        "STEP_UP",
                        "EMAIL_CHANGE",
                        "PHONE_CHANGE",
                        "PASSWORD_RESET",
                    ],
                ),
                name="ck_mfa_purpose_valid",
            ),
        ),
    ]
