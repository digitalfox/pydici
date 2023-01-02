# coding: utf-8
from django.db import migrations, models
from django.conf import settings

from django_celery_beat.models import CrontabSchedule, PeriodicTask


def add_tasks(apps, schema_editor):
    c, _ = CrontabSchedule.objects.get_or_create(minute=0, hour=6, day_of_week="*",
                                              day_of_month="*", month_of_year="*",
                                              timezone=settings.TIME_ZONE)
    t = PeriodicTask.objects.create(name="compute all consultants tasks", task="people.tasks.compute_all_consultants_tasks", crontab=c)


def remove_tasks(apps, schema_editor):
    PeriodicTask.objects.filter(task="people.tasks.compute_all_consultants_tasks").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("people", "0008_consultant_telegram_id"),
        ("core", "0012_create_default_periodic_tasks")
    ]

    operations = [
        migrations.RunPython(add_tasks, remove_tasks),
    ]
