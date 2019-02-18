# -*- coding: utf-8 -*-


from django.db import migrations, models

def add_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    p = Parameter.objects.get(key="MAIL_FROM ")
    p.key = "MAIL_FROM"
    p.save()


def remove_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    Parameter = apps.get_model("core", "Parameter")
    p = Parameter.objects.get(key="MAIL_FROM")
    p.key = "MAIL_FROM "
    p.save()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_fiscal_year'),
    ]

    operations = [
        migrations.RunPython(add_default_parameters, remove_default_parameters),
    ]
