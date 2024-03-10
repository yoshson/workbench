# Generated by Django 5.0.2 on 2024-03-10 14:39

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("invoices", "0026_alter_invoice_tax_rate_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="archived_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="archived at"
            ),
        ),
        migrations.RunSQL(
            "update invoices_invoice set archived_at=now() where invoiced_on is not null and invoiced_on <= '2023-12-31' and status > 10",
            "",
        ),
    ]