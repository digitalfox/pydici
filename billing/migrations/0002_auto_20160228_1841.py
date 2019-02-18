# -*- coding: utf-8 -*-


from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clientbill',
            name='creation_date',
            field=models.DateField(default=datetime.date.today, verbose_name='Creation date'),
        ),
        migrations.AlterField(
            model_name='supplierbill',
            name='creation_date',
            field=models.DateField(default=datetime.date.today, verbose_name='Creation date'),
        ),
    ]
