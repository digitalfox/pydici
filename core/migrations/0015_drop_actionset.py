# coding: utf-8
from django.db import migrations, models
from django.conf import settings

from django_celery_beat.models import CrontabSchedule, PeriodicTask


DROP_ACTIONSET_TABLES = """
drop table if exists actionset_actionstate;
drop table if exists actionset_action;
drop table if exists actionset_actionset;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_fix_periodict_tasks_scheduling"),
    ]

    operations = [
        migrations.RunSQL(DROP_ACTIONSET_TABLES),
    ]
