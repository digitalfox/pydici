# Generated by Django 3.2.19 on 2023-05-07 16:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0024_clientbill_billing_cli_state_e1a3c4_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientbill',
            name='add_facturx_data',
            field=models.BooleanField(default=False, verbose_name='Add Factur-X embedded information'),
        ),
    ]
