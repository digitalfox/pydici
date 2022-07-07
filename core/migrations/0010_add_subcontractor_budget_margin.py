# -*- coding: utf-8 -*-
from django.db import migrations, models


def add_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    Parameter.objects.bulk_create([
        Parameter(key="SUBCONTRACTOR_BUDGET_MARGIN", value="15", type="FLOAT",
                  desc="% (0-100) of objective margin for subcontractors."),
    ])


def remove_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    Parameter.objects.filter(key="SUBCONTRACTOR_BUDGET_MARGIN").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_add_bot_timesheet_time'),
    ]

    operations = [
        migrations.RunPython(add_default_parameters, remove_default_parameters),
    ]
