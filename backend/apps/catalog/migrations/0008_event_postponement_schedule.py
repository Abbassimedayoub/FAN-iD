from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_event_scanner_assignments"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="postponed_from_starts_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="postponed_from_ends_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="postponed_to_starts_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="postponed_to_ends_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
    ]
