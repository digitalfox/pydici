# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0003_add_address_and_billing_adress'),
    ]

    operations = [
        migrations.AddField(
            model_name='subsidiary',
            name='payment_description',
            field=models.TextField(null=True, verbose_name='Payment condition description', blank=True),
        ),
    ]
