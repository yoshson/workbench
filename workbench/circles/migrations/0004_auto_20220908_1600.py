# Generated by Django 3.2.14 on 2022-09-08 14:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0021_remove_service_role"),
        ("circles", "0003_role_work_category"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="role",
            name="circle",
        ),
        migrations.DeleteModel(
            name="Circle",
        ),
        migrations.DeleteModel(
            name="Role",
        ),
    ]