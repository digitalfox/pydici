# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from decimal import Decimal
import billing.models


class Migration(migrations.Migration):

    dependencies = [
        ('expense', '__first__'),
        ('crm', '__first__'),
        ('leads', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClientBill',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('bill_id', models.CharField(unique=True, max_length=200, verbose_name='Bill id')),
                ('creation_date', models.DateField(auto_now_add=True, verbose_name='Creation date')),
                ('due_date', models.DateField(default=billing.models.default_due_date, verbose_name='Due date')),
                ('payment_date', models.DateField(null=True, verbose_name='Payment date', blank=True)),
                ('previous_year_bill', models.BooleanField(default=False, verbose_name='Previous year bill')),
                ('comment', models.CharField(max_length=500, null=True, verbose_name='Comments', blank=True)),
                ('amount', models.DecimalField(verbose_name='Amount (\u20ac excl tax)', max_digits=10, decimal_places=2)),
                ('amount_with_vat', models.DecimalField(null=True, verbose_name='Amount (\u20ac incl tax)', max_digits=10, decimal_places=2, blank=True)),
                ('vat', models.DecimalField(default=Decimal('20.0'), verbose_name='VAT (%)', max_digits=4, decimal_places=2)),
                ('expenses_with_vat', models.BooleanField(default=True, verbose_name='Charge expense with VAT')),
                ('state', models.CharField(default=b'1_SENT', max_length=30, verbose_name='State', choices=[(b'1_SENT', 'Envoy\xe9e'), (b'2_PAID', 'Pay\xe9e'), (b'3_LITIGIOUS', 'En litige'), (b'4_CANCELED', 'Annul\xe9e')])),
                ('bill_file', models.FileField(storage=billing.models.BillStorage(nature=b'client'), upload_to=billing.models.bill_file_path, max_length=500, verbose_name='File')),
                ('expenses', models.ManyToManyField(to='expense.Expense', blank=True)),
                ('lead', models.ForeignKey(verbose_name='Lead', to='leads.Lead')),
            ],
            options={
                'verbose_name': 'Client Bill',
            },
        ),
        migrations.CreateModel(
            name='SupplierBill',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('bill_id', models.CharField(unique=True, max_length=200, verbose_name='Bill id')),
                ('creation_date', models.DateField(auto_now_add=True, verbose_name='Creation date')),
                ('due_date', models.DateField(default=billing.models.default_due_date, verbose_name='Due date')),
                ('payment_date', models.DateField(null=True, verbose_name='Payment date', blank=True)),
                ('previous_year_bill', models.BooleanField(default=False, verbose_name='Previous year bill')),
                ('comment', models.CharField(max_length=500, null=True, verbose_name='Comments', blank=True)),
                ('amount', models.DecimalField(verbose_name='Amount (\u20ac excl tax)', max_digits=10, decimal_places=2)),
                ('amount_with_vat', models.DecimalField(null=True, verbose_name='Amount (\u20ac incl tax)', max_digits=10, decimal_places=2, blank=True)),
                ('vat', models.DecimalField(default=Decimal('20.0'), verbose_name='VAT (%)', max_digits=4, decimal_places=2)),
                ('expenses_with_vat', models.BooleanField(default=True, verbose_name='Charge expense with VAT')),
                ('state', models.CharField(default=b'1_RECEIVED', max_length=30, verbose_name='State', choices=[(b'1_RECEIVED', 'Re\xe7ue'), (b'2_PAID', 'Pay\xe9e'), (b'3_LITIGIOUS', 'En litige'), (b'4_CANCELED', 'Annul\xe9e')])),
                ('bill_file', models.FileField(storage=billing.models.BillStorage(nature=b'supplier'), upload_to=billing.models.bill_file_path, max_length=500, verbose_name='File')),
                ('supplier_bill_id', models.CharField(max_length=200, verbose_name='Supplier Bill id')),
                ('expenses', models.ManyToManyField(to='expense.Expense', blank=True)),
                ('lead', models.ForeignKey(verbose_name='Lead', to='leads.Lead')),
                ('supplier', models.ForeignKey(to='crm.Supplier')),
            ],
            options={
                'verbose_name': 'Supplier Bill',
            },
        ),
        migrations.AlterUniqueTogether(
            name='supplierbill',
            unique_together=set([('supplier', 'supplier_bill_id')]),
        ),
    ]
