# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0009_auto_20180810_1715'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientbill',
            name='anonymize_profile',
            field=models.BooleanField(default=False, verbose_name='Anonymize profile name'),
        ),
    ]
