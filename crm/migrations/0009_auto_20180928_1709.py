# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0008_client_billing_contact'),
    ]

    operations = [
        migrations.AlterField(
            model_name='client',
            name='billing_contact',
            field=models.ForeignKey(verbose_name='Billing contact', blank=True, to='crm.AdministrativeContact', null=True),
        ),
    ]
