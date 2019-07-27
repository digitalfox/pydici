# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0006_auto_20180713_1851'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clientbill',
            name='state',
            field=models.CharField(default='0_DRAFT', max_length=30, verbose_name='State', choices=[('0_DRAFT', 'Draft'), ('0_PROPOSED', 'Proposed'), ('1_SENT', 'Sent'), ('2_PAID', 'Paid'), ('3_LITIGIOUS', 'Litigious'), ('4_CANCELED', 'Canceled')]),
        ),
    ]
