# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0005_auto_20180713_1914'),
    ]

    operations = [
        migrations.AddField(
            model_name='subsidiary',
            name='commercial_name',
            field=models.CharField(default='Please define commercial name of this subsidiary', max_length=200, verbose_name='Commercial name'),
            preserve_default=False,
        ),
    ]
