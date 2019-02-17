# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0002_fix_description_for_markdown'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='administrative_notes',
            field=models.TextField(verbose_name='Administrative notes', blank=True),
        ),
    ]
