# Generated by Django 3.2.14 on 2022-09-10 10:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0026_remove_internaltype_assigned_users"),
    ]

    operations = [
        migrations.AddField(
            model_name="internaltype",
            name="description",
            field=models.CharField(
                blank=True, max_length=100, verbose_name="description"
            ),
        ),
    ]
