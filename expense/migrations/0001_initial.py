# -*- coding: utf-8 -*-


from django.db import models, migrations
import expense.models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('leads', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=200, verbose_name='Description')),
                ('chargeable', models.BooleanField(verbose_name='Chargeable')),
                ('creation_date', models.DateField(verbose_name='Date')),
                ('expense_date', models.DateField(verbose_name='Expense date')),
                ('update_date', models.DateTimeField(auto_now=True, verbose_name='Updated')),
                ('amount', models.DecimalField(verbose_name='Amount', max_digits=7, decimal_places=2)),
                ('receipt', models.FileField(upload_to=expense.models.expense_receipt_path, storage=expense.models.ExpenseStorage(), max_length=500, blank=True, null=True, verbose_name='Receipt')),
                ('corporate_card', models.BooleanField(default=False, verbose_name='Paid with corporate card')),
                ('comment', models.TextField(verbose_name='Comments', blank=True)),
                ('workflow_in_progress', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['-expense_date'],
                'verbose_name': 'Expense',
                'verbose_name_plural': 'Expenses',
            },
        ),
        migrations.CreateModel(
            name='ExpenseCategory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=50, verbose_name='Name')),
            ],
            options={
                'verbose_name': 'Expense category',
                'verbose_name_plural': 'Expense categories',
            },
        ),
        migrations.CreateModel(
            name='ExpensePayment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('payment_date', models.DateField(verbose_name='Payment date')),
            ],
            options={
                'verbose_name': 'Expenses payment',
                'verbose_name_plural': 'Expenses payments',
            },
        ),
        migrations.AddField(
            model_name='expense',
            name='category',
            field=models.ForeignKey(verbose_name='Category', to='expense.ExpenseCategory', on_delete=models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='expense',
            name='expensePayment',
            field=models.ForeignKey(blank=True, to='expense.ExpensePayment', null=True, on_delete=models.deletion.SET_NULL),
        ),
        migrations.AddField(
            model_name='expense',
            name='lead',
            field=models.ForeignKey(verbose_name='Lead', blank=True, to='leads.Lead', null=True, on_delete=models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='expense',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.deletion.CASCADE),
        ),
    ]
