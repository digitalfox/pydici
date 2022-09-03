# coding: utf-8
from django.db import migrations, models
from django.conf import settings

from django_celery_beat.models import CrontabSchedule, PeriodicTask


def update_scheduling(apps, schema_editor):
    c = CrontabSchedule.objects.get(minute=0, hour=6, day_of_week="0-5",
                                    day_of_month="*", month_of_year="*",
                                    timezone=settings.TIME_ZONE)
    c.day_of_month = "2-31"
    c.save()


def undo_update_scheduling(apps, schema_editor):
    c = CrontabSchedule.objects.get(minute=0, hour=6, day_of_week="0-5",
                                    day_of_month="2-31", month_of_year="*",
                                    timezone=settings.TIME_ZONE)
    c.day_of_month = "*"
    c.save()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0013_alter_groupfeature_feature"),
    ]

    operations = [
        migrations.RunPython(update_scheduling, undo_update_scheduling),
    ]
