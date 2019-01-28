# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0011_auto_20180905_1940'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientbill',
            name='lang',
            field=models.CharField(default='fr-fr', max_length=10, verbose_name='Lang'),
        ),
    ]
