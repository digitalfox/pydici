# -*- coding: utf-8 -*-


from django.db import migrations
from django.db.models import F, Func, Value

def fix_list(apps, schema_editor):
    Lead = apps.get_model("leads", "Lead")
    # Use bulk update to avoid triggering default Lead.save, signals and date field auto update.
    Lead.objects.all().update(description=Func(F("description"), Value(": \n"), Value(":\n"), function="replace"))
    Lead.objects.all().update(description=Func(F("description"), Value(":\n-"), Value(":\n\n-"), function="replace"))


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(fix_list),
    ]
