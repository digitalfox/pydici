# -*- coding: utf-8 -*-


from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0009_auto_20180928_1709'),
    ]

    operations = [
        migrations.AlterField(
            model_name='client',
            name='billing_contact',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, verbose_name='Billing contact', blank=True, to='crm.AdministrativeContact', null=True),
        ),
    ]
