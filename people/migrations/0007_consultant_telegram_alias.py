# Generated by Django 2.2.13 on 2021-01-16 18:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0006_auto_20190310_2209'),
    ]

    operations = [
        migrations.AddField(
            model_name='consultant',
            name='telegram_alias',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
