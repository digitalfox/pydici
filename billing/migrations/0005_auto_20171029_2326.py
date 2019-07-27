# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0004_allow_null_in_bill_detail'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billexpense',
            name='amount_with_vat',
            field=models.DecimalField(null=True, verbose_name='Amount (\u20ac incl tax)', max_digits=10, decimal_places=2, blank=True),
        ),
        migrations.AlterField(
            model_name='billexpense',
            name='expense',
            field=models.ForeignKey(verbose_name='Expense', to='expense.Expense', on_delete=models.deletion.SET_NULL),
        ),
        migrations.AlterField(
            model_name='billexpense',
            name='expense_date',
            field=models.DateField(null=True, verbose_name='Expense date'),
        ),
        migrations.AlterField(
            model_name='billexpense',
            name='label',
            field=models.CharField(max_length=200, null=True, verbose_name='Description', blank=True),
        ),
        migrations.AlterField(
            model_name='clientbill',
            name='vat',
            field=models.DecimalField(default=20.0, verbose_name='VAT (%)', max_digits=4, decimal_places=2),
        ),
        migrations.AlterField(
            model_name='supplierbill',
            name='vat',
            field=models.DecimalField(default=20.0, verbose_name='VAT (%)', max_digits=4, decimal_places=2),
        ),
    ]
