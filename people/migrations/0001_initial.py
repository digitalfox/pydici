# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Consultant',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=50)),
                ('trigramme', models.CharField(unique=True, max_length=4)),
                ('productive', models.BooleanField(default=True, verbose_name='Productive')),
                ('active', models.BooleanField(default=True, verbose_name='Active')),
                ('subcontractor', models.BooleanField(default=False, verbose_name='Subcontractor')),
                ('subcontractor_company', models.CharField(max_length=200, null=True, blank=True)),
                ('company', models.ForeignKey(verbose_name='Subsidiary', to='crm.Subsidiary', on_delete=models.CASCADE)),
                ('manager', models.ForeignKey(related_name='team_as_manager', blank=True, to='people.Consultant', null=True, on_delete=models.SET_NULL)),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'Consultant',
            },
        ),
        migrations.CreateModel(
            name='ConsultantProfile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=50, verbose_name='Name')),
                ('level', models.IntegerField(verbose_name='Level')),
            ],
            options={
                'ordering': ['level'],
                'verbose_name': 'Consultant profile',
            },
        ),
        migrations.CreateModel(
            name='RateObjective',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('start_date', models.DateField(verbose_name='Starting')),
                ('daily_rate', models.IntegerField(verbose_name='Daily rate')),
                ('consultant', models.ForeignKey(to='people.Consultant', on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='SalesMan',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=50, verbose_name='Name')),
                ('trigramme', models.CharField(unique=True, max_length=4)),
                ('active', models.BooleanField(default=True, verbose_name='Active')),
                ('email', models.EmailField(max_length=254, blank=True)),
                ('phone', models.CharField(max_length=30, verbose_name='Phone', blank=True)),
                ('company', models.ForeignKey(verbose_name='Subsidiary', to='crm.Subsidiary', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'Salesman',
                'verbose_name_plural': 'Salesmen',
            },
        ),
        migrations.AddField(
            model_name='consultant',
            name='profil',
            field=models.ForeignKey(verbose_name='Profil', to='people.ConsultantProfile', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='consultant',
            name='staffing_manager',
            field=models.ForeignKey(related_name='team_as_staffing_manager', blank=True, to='people.Consultant', null=True, on_delete=models.SET_NULL),
        ),
    ]
