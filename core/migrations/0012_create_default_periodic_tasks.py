# coding: utf-8
from django.db import migrations, models
from django.conf import settings

from django_celery_beat.models import CrontabSchedule, PeriodicTask


def add_default_tasks(apps, schema_editor):
    c = CrontabSchedule.objects.create(minute=0, hour=6, day_of_week="*",
                                       day_of_month="*", month_of_year="*",
                                       timezone=settings.TIME_ZONE)
    t = PeriodicTask.objects.create(name="session cleanup", task="core.tasks.sessions_cleanup", crontab=c)

    c = CrontabSchedule.objects.create(minute=0, hour=6, day_of_week="*",
                                       day_of_month="1", month_of_year="*",
                                       timezone=settings.TIME_ZONE)
    t = PeriodicTask.objects.create(name="Warn users for incomplete timesheet and overbooking on last month",
                                    task="staffing.tasks.warn_for_incomplete_timesheet",
                                    kwargs='''{"warn_overbooking": true, "days": null, "month": "last"}''',
                                    crontab=c)

    c = CrontabSchedule.objects.create(minute=0, hour=6, day_of_week="0-5",
                                       day_of_month="*", month_of_year="*",
                                       timezone=settings.TIME_ZONE)
    t = PeriodicTask.objects.create(name="Warn users for incomplete timesheet on last month",
                                    task="staffing.tasks.warn_for_incomplete_timesheet",
                                    kwargs='''{"warn_overbooking": false, "days": null, "month": "last"}''',
                                    crontab=c)

    c = CrontabSchedule.objects.create(minute=0, hour=6, day_of_week="0-5",
                                       day_of_month="21-31", month_of_year="*",
                                       timezone=settings.TIME_ZONE)
    t = PeriodicTask.objects.create(name="Warn users for incomplete timesheet on current month",
                                    task="staffing.tasks.warn_for_incomplete_timesheet",
                                    kwargs='''{"warn_overbooking": false, "days": 20, "month": "current"}''',
                                    crontab=c)


def remove_default_tasks(apps, schema_editor):
    CrontabSchedule.objects.all().delete()  # Will remove all related periodic tasks with cascade


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0011_alter_groupfeature_feature'),
    ]

    operations = [
        migrations.RunPython(add_default_tasks, remove_default_tasks),
    ]
