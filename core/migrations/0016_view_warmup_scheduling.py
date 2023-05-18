# coding: utf-8
from django.db import migrations, models
from django.conf import settings

from django_celery_beat.models import CrontabSchedule, PeriodicTask


def add_warmup_task(apps, schema_editor):
    c, created = CrontabSchedule.objects.get_or_create(minute=0, hour=6, day_of_week="*",
                                       day_of_month="*", month_of_year="*",
                                       timezone=settings.TIME_ZONE)
    t = PeriodicTask.objects.create(name="view warmup", task="core.tasks.view_warmup", crontab=c)



def remove_warmup_task(apps, schema_editor):
    t = PeriodicTask.objects.get(name="view warmup", task="core.tasks.view_warmup")
    t.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0015_drop_actionset"),
        ("django_celery_beat", "0016_alter_crontabschedule_timezone")
    ]

    operations = [
        migrations.RunPython(add_warmup_task, remove_warmup_task),
    ]
