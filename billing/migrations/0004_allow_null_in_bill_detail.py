# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0003_add_bill_detail_and_bill_expense'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billdetail',
            name='consultant',
            field=models.ForeignKey(blank=True, to='people.Consultant', null=True, on_delete=models.deletion.CASCADE),
        ),
        migrations.AlterField(
            model_name='billdetail',
            name='quantity',
            field=models.FloatField(null=True, verbose_name='Quantity', blank=True),
        ),
        migrations.AlterField(
            model_name='billdetail',
            name='unit_price',
            field=models.DecimalField(null=True, verbose_name='Unit price (\u20ac)', max_digits=10, decimal_places=2, blank=True),
        ),
        migrations.AlterField(
            model_name='billdetail',
            name='vat',
            field=models.DecimalField(default=20.0, verbose_name='VAT (%)', max_digits=4, decimal_places=2),
        ),
        migrations.AlterField(
            model_name='billdetail',
            name='month',
            field=models.DateField(null=True),
        ),
    ]
