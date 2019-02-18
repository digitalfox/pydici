# -*- coding: utf-8 -*-


from django.db import migrations, models
import billing.models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0005_auto_20171029_2326'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clientbill',
            name='bill_id',
            field=models.CharField(default=billing.models.default_bill_id, unique=True, max_length=200, verbose_name='Bill id'),
        ),
        migrations.AlterField(
            model_name='supplierbill',
            name='bill_id',
            field=models.CharField(default=billing.models.default_bill_id, unique=True, max_length=200, verbose_name='Bill id'),
        ),
    ]
