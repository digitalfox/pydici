# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0008_billexpense_amount'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billdetail',
            name='quantity',
            field=models.FloatField(default=1, verbose_name='Quantity'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='billdetail',
            name='unit_price',
            field=models.DecimalField(default=1000, verbose_name='Unit price (\u20ac)', max_digits=10, decimal_places=2),
            preserve_default=False,
        ),
    ]
