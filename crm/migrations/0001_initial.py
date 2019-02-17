# -*- coding: utf-8 -*-


from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Subsidiary',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=200, verbose_name='Name')),
                ('code', models.CharField(unique=True, max_length=3, verbose_name='Code')),
                ('web', models.URLField(null=True, blank=True)),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'Subsidiary',
                'verbose_name_plural': 'Subsidiaries',
            },
        ),
    ]
