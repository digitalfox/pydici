# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0007_client_billing_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='billing_contact',
            field=models.ForeignKey(to='crm.AdministrativeContact', null=True, on_delete=models.SET_NULL),
        ),
    ]
