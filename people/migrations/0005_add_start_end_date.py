# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from datetime import date

from django.db import migrations, models
from django.db.models import Min, Max

def set_default_values(apps, schema_editor):
    from people.models import Consultant
    for consultant in Consultant.objects.all():
        consultant_dates = consultant.timesheet_set.aggregate(Min("working_date"), Max("working_date"))
        start = consultant_dates["working_date__min"]
        end = consultant_dates["working_date__max"]
        if not consultant.start_date:
            consultant.start_date = start or date.today()
        if not consultant.active:
            consultant.end_date = end or date.today()
        consultant.save()

class Migration(migrations.Migration):

    dependencies = [
        ('people', '0004_auto_20170817_2015'),
    ]

    operations = [
        migrations.AddField(
            model_name='consultant',
            name='end_date',
            field=models.DateField(null=True, blank=True, verbose_name='Leaving date'),
        ),
        migrations.AddField(
            model_name='consultant',
            name='start_date',
            field=models.DateField(default=date.today, verbose_name='Arrival date', null=True),
        ),
        migrations.RunPython(set_default_values, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='consultant',
            name='start_date',
            field=models.DateField(default=date.today, verbose_name='Arrival date'),
        ),
    ]
