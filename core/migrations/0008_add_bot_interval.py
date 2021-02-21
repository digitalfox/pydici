# -*- coding: utf-8 -*-


from django.db import migrations, models

def add_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    Parameter.objects.bulk_create([
        Parameter(key="BOT_ALERT_INTERVAL", value="1800", type="FLOAT",
                  desc="Interval (in sec) between two warnings sent by pydici telegram bot"),
    ])


def remove_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    Parameter.objects.filter(key="BOT_ALERT_INTERVAL").delete()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_auto_20201212_1430'),
    ]

    operations = [
        migrations.RunPython(add_default_parameters, remove_default_parameters),
    ]
