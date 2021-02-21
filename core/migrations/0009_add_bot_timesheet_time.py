# -*- coding: utf-8 -*-


from django.db import migrations, models


def add_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    Parameter.objects.bulk_create([
        Parameter(key="BOT_CALL_TIME_FOR_TIMESHEET", value="18:45", type="TEXT",
                  desc="Time (in format hours:min ex. 18:45) for calling people to declare their timesheet"),
    ])


def remove_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    Parameter.objects.filter(key="BOT_CALL_TIME_FOR_TIMESHEET").delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0008_add_bot_interval'),
    ]

    operations = [
        migrations.RunPython(add_default_parameters, remove_default_parameters),
    ]
