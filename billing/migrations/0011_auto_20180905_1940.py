# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0010_clientbill_anonymize_profile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billexpense',
            name='expense',
            field=models.ForeignKey(verbose_name='Expense', blank=True, to='expense.Expense', null=True, on_delete=models.deletion.SET_NULL),
        ),
    ]
