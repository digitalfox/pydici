# -*- coding: utf-8 -*-


from django.db import migrations, models

def add_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    Parameter.objects.bulk_create([
        Parameter(key="FISCAL_YEAR_MONTH", value="1", type="FLOAT",
                  desc="Fiscal year start. 1 for janury, 6 for june etc."),
    ])


def remove_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    Parameter.objects.filter(key="FISCAL_YEAR_MONTH").delete()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_parameter'),
    ]

    operations = [
        migrations.RunPython(add_default_parameters, remove_default_parameters),
    ]
