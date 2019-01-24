# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0006_auto_20180713_1851'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clientbill',
            name='state',
            field=models.CharField(default=b'0_DRAFT', max_length=30, verbose_name='State', choices=[(b'0_DRAFT', 'Draft'), (b'0_PROPOSED', 'Proposed'), (b'1_SENT', 'Sent'), (b'2_PAID', 'Paid'), (b'3_LITIGIOUS', 'Litigious'), (b'4_CANCELED', 'Canceled')]),
        ),
    ]
