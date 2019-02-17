# -*- coding: utf-8 -*-


from django.db import migrations, models
import billing.models


class Migration(migrations.Migration):

    dependencies = [
        ('expense', '0001_initial'),
        ('staffing', '0003_auto_20160228_1841'),
        ('billing', '0002_auto_20160228_1841'),
    ]

    operations = [
        migrations.CreateModel(
            name='BillDetail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('month', models.DateField(null=True, blank=True)),
                ('quantity', models.FloatField(verbose_name='Quantity')),
                ('unit_price', models.DecimalField(verbose_name='Unit price (\u20ac)', max_digits=10, decimal_places=2)),
                ('amount', models.DecimalField(null=True, verbose_name='Amount (\u20ac excl tax)', max_digits=10, decimal_places=2, blank=True)),
                ('amount_with_vat', models.DecimalField(null=True, verbose_name='Amount (\u20ac incl tax)', max_digits=10, decimal_places=2, blank=True)),
                ('vat', models.DecimalField(default='20.0', verbose_name='VAT (%)', max_digits=4, decimal_places=2)),
                ('label', models.CharField(max_length=200, null=True, verbose_name='Label', blank=True)),
            ],
            options={
                'ordering': ('mission', 'month', 'consultant'),
            },
        ),
        migrations.CreateModel(
            name='BillExpense',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('expense_date', models.DateField()),
                ('amount_with_vat', models.DecimalField(verbose_name='Amount (\u20ac incl tax)', max_digits=10, decimal_places=2)),
                ('label', models.CharField(max_length=200, null=True, verbose_name='Label', blank=True)),
            ],
            options={
                'ordering': ('expense_date',),
            },
        ),
        migrations.AlterField(
            model_name='clientbill',
            name='amount',
            field=models.DecimalField(null=True, verbose_name='Amount (\u20ac excl tax)', max_digits=10, decimal_places=2, blank=True),
        ),
        migrations.AlterField(
            model_name='clientbill',
            name='bill_file',
            field=models.FileField(upload_to=billing.models.bill_file_path, storage=billing.models.BillStorage(nature='client'), max_length=500, blank=True, null=True, verbose_name='File'),
        ),
        migrations.AlterField(
            model_name='clientbill',
            name='state',
            field=models.CharField(default='0_DRAFT', max_length=30, verbose_name='State', choices=[('0_DRAFT', 'Draft'), ('1_SENT', 'Envoy\xe9e'), ('2_PAID', 'Pay\xe9e'), ('3_LITIGIOUS', 'En litige'), ('4_CANCELED', 'Annul\xe9e')]),
        ),
        migrations.AlterField(
            model_name='clientbill',
            name='vat',
            field=models.DecimalField(default='20.0', verbose_name='VAT (%)', max_digits=4, decimal_places=2),
        ),
        migrations.AlterField(
            model_name='supplierbill',
            name='amount',
            field=models.DecimalField(null=True, verbose_name='Amount (\u20ac excl tax)', max_digits=10, decimal_places=2, blank=True),
        ),
        migrations.AlterField(
            model_name='supplierbill',
            name='vat',
            field=models.DecimalField(default='20.0', verbose_name='VAT (%)', max_digits=4, decimal_places=2),
        ),
        migrations.AddField(
            model_name='billexpense',
            name='bill',
            field=models.ForeignKey(to='billing.ClientBill', on_delete=models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='billexpense',
            name='expense',
            field=models.ForeignKey(to='expense.Expense', on_delete=models.deletion.SET_NULL),
        ),
        migrations.AddField(
            model_name='billdetail',
            name='bill',
            field=models.ForeignKey(to='billing.ClientBill', on_delete=models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='billdetail',
            name='consultant',
            field=models.ForeignKey(to='people.Consultant', null=True, on_delete=models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='billdetail',
            name='mission',
            field=models.ForeignKey(to='staffing.Mission', on_delete=models.deletion.CASCADE),
        ),
    ]
