# -*- coding: utf-8 -*-
from django.db import migrations, models


def add_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    Parameter.objects.bulk_create([
        Parameter(key="INTERNAL_MARKUP", value="10", type="FLOAT",
                  desc="% (0-100) of markup. Used to compute internal rate between subsidiaries from client mission rate."),
    ])


def remove_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    Parameter.objects.filter(key="INTERNAL_MARKUP").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_view_warmup_scheduling'),
    ]

    operations = [
        migrations.RunPython(add_default_parameters, remove_default_parameters),
    ]
