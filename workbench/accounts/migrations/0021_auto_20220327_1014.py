# Generated by Django 3.2.12 on 2022-03-27 08:14

from django.db import migrations
from django.utils.crypto import get_random_string


def forwards(apps, schema_editor):
    for u in apps.get_model("accounts", "user").objects.all():
        u.token = f"{get_random_string(60)}-{u.pk}"
        u.save()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0020_user_token"),
    ]

    operations = [
        migrations.RunPython(forwards),
    ]