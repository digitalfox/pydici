# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('staffing', '0002_auto_20160214_1402'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lunchticket',
            name='no_ticket',
            field=models.BooleanField(default=True, verbose_name='No lunch ticket'),
        ),
    ]
