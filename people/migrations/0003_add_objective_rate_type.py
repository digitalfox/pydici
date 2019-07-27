# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0002_rename_rateobjective_daily_rate_field_to_rate'),
    ]

    operations = [
        migrations.AddField(
            model_name='rateobjective',
            name='rate_type',
            field=models.CharField(default='DAILY_RATE', max_length=30, verbose_name='Rate type', choices=[('DAILY_RATE', 'daily rate'), ('PROD_RATE', 'production rate')]),
            preserve_default=False,
        ),
    ]
