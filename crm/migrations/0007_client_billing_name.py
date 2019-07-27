# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0006_subsidiary_commercial_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='billing_name',
            field=models.CharField(max_length=200, null=True, verbose_name='Name used for billing', blank=True),
        ),
    ]
