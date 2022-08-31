# coding: utf-8
from django.db import migrations, models
from django.conf import settings

from django_celery_beat.models import CrontabSchedule, PeriodicTask


def add_default_tasks(apps, schema_editor):
    c, _ = CrontabSchedule.objects.get_or_create(minute=0, hour=6, day_of_week="*",
                                              day_of_month="*", month_of_year="*",
                                              timezone=settings.TIME_ZONE)
    t = PeriodicTask.objects.create(name="learning model warm up", task="leads.tasks.learning_warmup", crontab=c)


def remove_default_tasks(apps, schema_editor):
    PeriodicTask.objects.filter(task="leads.tasks.learning_warmup").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("leads", "0005_auto_20190819_1519"),
        ("core", "0012_create_default_periodic_tasks")
    ]

    operations = [
        migrations.RunPython(add_default_tasks, remove_default_tasks),
    ]
