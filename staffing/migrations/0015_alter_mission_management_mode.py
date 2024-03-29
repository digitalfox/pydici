# Generated by Django 3.2.16 on 2023-02-02 09:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('staffing', '0014_mission_min_charge_per_day'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mission',
            name='management_mode',
            field=models.CharField(choices=[('LIMITED', 'Limité'), ('LIMITED_INDIVIDUAL', 'Limited individual'), ('ELASTIC', 'Élastique'), ('NONE', 'Aucun')], default='NONE', max_length=30, verbose_name='Management mode'),
        ),
    ]
