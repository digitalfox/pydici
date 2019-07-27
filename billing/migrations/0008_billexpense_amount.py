# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0007_auto_20180717_1636'),
    ]

    operations = [
        migrations.AddField(
            model_name='billexpense',
            name='amount',
            field=models.DecimalField(null=True, verbose_name='Amount (\u20ac excl tax)', max_digits=10, decimal_places=2, blank=True),
        ),
    ]
