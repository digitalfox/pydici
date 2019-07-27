# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0012_clientbill_lang'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clientbill',
            name='lang',
            field=models.CharField(default='fr-fr', max_length=10, verbose_name='Language', choices=[('fr-fr', 'French'), ('en-en', 'English')]),
        ),
    ]
