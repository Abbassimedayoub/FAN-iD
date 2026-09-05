from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0008_event_postponement_schedule"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="sales_starts_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="sales_ends_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="event",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        sales_starts_at__isnull=True,
                    )
                    | models.Q(
                        sales_ends_at__isnull=True,
                    )
                    | models.Q(
                        sales_ends_at__gt=models.F(
                            "sales_starts_at"
                        ),
                    )
                ),
                name="ck_event_sales_window_coherent",
            ),
        ),
    ]
