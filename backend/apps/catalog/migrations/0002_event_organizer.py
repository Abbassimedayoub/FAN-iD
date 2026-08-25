import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F
from django.db.models.functions import Lower


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
        ("organizing", "0001_initial"),
    ]

    operations = [
        # Nullable only as a compatibility bridge for events created
        # before organizer ownership existed.
        migrations.AddField(
            model_name="event",
            name="organizer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="events",
                to="organizing.organizer",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="event",
            name="uq_event_name_ci",
        ),
        migrations.AddConstraint(
            model_name="event",
            constraint=models.UniqueConstraint(
                Lower("name"),
                F("organizer"),
                name="uq_event_org_name_ci",
            ),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(
                fields=["organizer"],
                name="ix_event_organizer",
            ),
        ),
    ]
