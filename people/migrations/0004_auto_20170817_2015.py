# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0003_add_objective_rate_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rateobjective',
            name='rate',
            field=models.IntegerField(null=True, verbose_name='Rate'),
        ),
    ]
