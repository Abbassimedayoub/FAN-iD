from django.db import migrations, models


def backfill_legacy_agreements(
    apps,
    schema_editor,
):
    Organizer = apps.get_model(
        "organizing",
        "Organizer",
    )

    queryset = Organizer.objects.filter(
        validation_status__in=[
            "APPROVED",
            "SUSPENDED",
        ],
        commission_agreed_at__isnull=True,
    )

    for organizer in queryset.iterator():
        agreed_at = (
            organizer.validated_at
            or organizer.updated_at
            or organizer.created_at
        )

        Organizer.objects.filter(
            pk=organizer.pk,
        ).update(
            commission_agreed_at=agreed_at,
        )


def noop_reverse(
    apps,
    schema_editor,
):
    return None


class Migration(migrations.Migration):

    dependencies = [
        (
            "organizing",
            "0011_organizer_commission_proposal",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="organizer",
            name="commission_agreed_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.RunPython(
            backfill_legacy_agreements,
            noop_reverse,
        ),
    ]
