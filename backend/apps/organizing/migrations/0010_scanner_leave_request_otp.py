from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "organizing",
            "0009_organizer_reactivation_request",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="scannerrevocationchallenge",
            name="action",
            field=models.CharField(
                choices=[
                    ("REVOKE", "REVOKE"),
                    (
                        "LEAVE_ACCEPT",
                        "LEAVE_ACCEPT",
                    ),
                    (
                        "LEAVE_REQUEST",
                        "LEAVE_REQUEST",
                    ),
                ],
                max_length=20,
            ),
        ),
    ]
