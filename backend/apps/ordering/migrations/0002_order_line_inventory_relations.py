# Generated manually for an empty local ordering dataset.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0009_event_sales_window"),
        ("ordering", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderline",
            name="ticket_category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="order_lines",
                to="catalog.ticketcategory",
            ),
        ),
        migrations.CreateModel(
            name="StockHoldLine",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("quantity", models.PositiveIntegerField()),
                (
                    "stock_hold",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lines",
                        to="ordering.stockhold",
                    ),
                ),
                (
                    "ticket_category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="stock_hold_lines",
                        to="catalog.ticketcategory",
                    ),
                ),
            ],
            options={
                "db_table": "ordering_stock_hold_line",
            },
        ),
        migrations.AddConstraint(
            model_name="stockholdline",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantity__gt", 0)),
                name="ck_stock_hold_line_quantity_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="stockholdline",
            constraint=models.UniqueConstraint(
                fields=("stock_hold", "ticket_category"),
                name="uq_stock_hold_line_hold_ticket",
            ),
        ),
        migrations.AddIndex(
            model_name="stockholdline",
            index=models.Index(
                fields=["ticket_category", "stock_hold"],
                name="ix_hold_line_ticket_hold",
            ),
        ),
    ]
