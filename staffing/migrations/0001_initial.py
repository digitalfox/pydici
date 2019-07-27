# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0001_initial'),
        ('people', '__first__'),
        ('leads', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='FinancialCondition',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('daily_rate', models.IntegerField(verbose_name='Daily rate')),
                ('bought_daily_rate', models.IntegerField(null=True, verbose_name='Bought daily rate', blank=True)),
                ('consultant', models.ForeignKey(to='people.Consultant', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name': 'Financial condition',
            },
        ),
        migrations.CreateModel(
            name='Holiday',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('day', models.DateField(verbose_name='Date')),
                ('description', models.CharField(max_length=200, verbose_name='Description')),
            ],
            options={
                'verbose_name': 'Holiday',
            },
        ),
        migrations.CreateModel(
            name='LunchTicket',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('lunch_date', models.DateField(verbose_name='Date')),
                ('no_ticket', models.BooleanField(verbose_name='No lunch ticket')),
                ('consultant', models.ForeignKey(to='people.Consultant', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name': 'Lunch ticket',
            },
        ),
        migrations.CreateModel(
            name='Mission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('deal_id', models.CharField(max_length=100, verbose_name='Mission id', blank=True)),
                ('description', models.CharField(max_length=30, null=True, verbose_name='Description', blank=True)),
                ('nature', models.CharField(default='PROD', max_length=30, verbose_name='Type', choices=[('PROD', 'Productif'), ('NONPROD', 'Non productif'), ('HOLIDAYS', 'Cong\xe9s')])),
                ('billing_mode', models.CharField(max_length=30, null=True, verbose_name='Billing mode', choices=[('FIXED_PRICE', 'Forfait'), ('TIME_SPENT', 'Temps pass\xe9')])),
                ('active', models.BooleanField(default=True, verbose_name='Active')),
                ('probability', models.IntegerField(default=50, verbose_name='Proba', choices=[(0, 'Null (0 %)'), (25, 'Faible (25 %)'), (50, 'Moyenne (50 %)'), (75, 'Haute (75 %)'), (100, 'Certaine (100 %)')])),
                ('probability_auto', models.BooleanField(default=True, verbose_name='Automatic probability')),
                ('price', models.DecimalField(null=True, verbose_name='Price (k\u20ac)', max_digits=10, decimal_places=3, blank=True)),
                ('update_date', models.DateTimeField(auto_now=True, verbose_name='Updated')),
                ('archived_date', models.DateTimeField(null=True, verbose_name='Archived date', blank=True)),
                ('contacts', models.ManyToManyField(to='crm.MissionContact', blank=True)),
                ('lead', models.ForeignKey(verbose_name='Lead', blank=True, to='leads.Lead', null=True, on_delete=models.CASCADE)),
                ('responsible', models.ForeignKey(related_name='mission_responsible', verbose_name='Responsible', blank=True, to='people.Consultant', null=True, on_delete=models.SET_NULL)),
                ('subsidiary', models.ForeignKey(verbose_name='Subsidiary', to='crm.Subsidiary', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['nature', 'lead__client__organisation__company', 'id', 'description'],
                'verbose_name': 'Mission',
            },
        ),
        migrations.CreateModel(
            name='Staffing',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('staffing_date', models.DateField(verbose_name='Date')),
                ('charge', models.FloatField(default=0, verbose_name='Load')),
                ('comment', models.CharField(max_length=500, null=True, verbose_name='Comments', blank=True)),
                ('update_date', models.DateTimeField(null=True, blank=True)),
                ('last_user', models.CharField(max_length=60, null=True, blank=True)),
                ('consultant', models.ForeignKey(to='people.Consultant', on_delete=models.CASCADE)),
                ('mission', models.ForeignKey(to='staffing.Mission', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['staffing_date', 'consultant'],
                'verbose_name': 'Staffing',
            },
        ),
        migrations.CreateModel(
            name='Timesheet',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('working_date', models.DateField(verbose_name='Date')),
                ('charge', models.FloatField(default=0, verbose_name='Load')),
                ('consultant', models.ForeignKey(to='people.Consultant', on_delete=models.CASCADE)),
                ('mission', models.ForeignKey(to='staffing.Mission', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['working_date', 'consultant'],
                'verbose_name': 'Timesheet',
            },
        ),
        migrations.AddField(
            model_name='financialcondition',
            name='mission',
            field=models.ForeignKey(to='staffing.Mission', on_delete=models.CASCADE),
        ),
        migrations.AlterUniqueTogether(
            name='timesheet',
            unique_together=set([('consultant', 'mission', 'working_date')]),
        ),
        migrations.AlterUniqueTogether(
            name='staffing',
            unique_together=set([('consultant', 'mission', 'staffing_date')]),
        ),
        migrations.AlterUniqueTogether(
            name='lunchticket',
            unique_together=set([('consultant', 'lunch_date')]),
        ),
        migrations.AlterUniqueTogether(
            name='financialcondition',
            unique_together=set([('consultant', 'mission', 'daily_rate')]),
        ),
    ]
