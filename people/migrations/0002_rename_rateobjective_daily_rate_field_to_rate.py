# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='rateobjective',
            old_name="daily_rate",
            new_name='rate',
        ),
    ]
