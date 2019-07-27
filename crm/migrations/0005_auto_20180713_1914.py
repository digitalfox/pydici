# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0004_subsidiary_payment_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='billing_city',
            field=models.CharField(max_length=200, null=True, verbose_name='City', blank=True),
        ),
        migrations.AddField(
            model_name='client',
            name='billing_country',
            field=models.CharField(max_length=50, null=True, verbose_name='Country', blank=True),
        ),
        migrations.AddField(
            model_name='client',
            name='billing_street',
            field=models.TextField(null=True, verbose_name='Street', blank=True),
        ),
        migrations.AddField(
            model_name='client',
            name='billing_zipcode',
            field=models.CharField(max_length=30, null=True, verbose_name='Zip code', blank=True),
        ),
        migrations.AddField(
            model_name='client',
            name='city',
            field=models.CharField(max_length=200, null=True, verbose_name='City', blank=True),
        ),
        migrations.AddField(
            model_name='client',
            name='country',
            field=models.CharField(max_length=50, null=True, verbose_name='Country', blank=True),
        ),
        migrations.AddField(
            model_name='client',
            name='street',
            field=models.TextField(null=True, verbose_name='Street', blank=True),
        ),
        migrations.AddField(
            model_name='client',
            name='zipcode',
            field=models.CharField(max_length=30, null=True, verbose_name='Zip code', blank=True),
        ),
        migrations.AddField(
            model_name='clientorganisation',
            name='billing_city',
            field=models.CharField(max_length=200, null=True, verbose_name='City', blank=True),
        ),
        migrations.AddField(
            model_name='clientorganisation',
            name='billing_country',
            field=models.CharField(max_length=50, null=True, verbose_name='Country', blank=True),
        ),
        migrations.AddField(
            model_name='clientorganisation',
            name='billing_street',
            field=models.TextField(null=True, verbose_name='Street', blank=True),
        ),
        migrations.AddField(
            model_name='clientorganisation',
            name='billing_zipcode',
            field=models.CharField(max_length=30, null=True, verbose_name='Zip code', blank=True),
        ),
        migrations.AddField(
            model_name='clientorganisation',
            name='city',
            field=models.CharField(max_length=200, null=True, verbose_name='City', blank=True),
        ),
        migrations.AddField(
            model_name='clientorganisation',
            name='country',
            field=models.CharField(max_length=50, null=True, verbose_name='Country', blank=True),
        ),
        migrations.AddField(
            model_name='clientorganisation',
            name='street',
            field=models.TextField(null=True, verbose_name='Street', blank=True),
        ),
        migrations.AddField(
            model_name='clientorganisation',
            name='zipcode',
            field=models.CharField(max_length=30, null=True, verbose_name='Zip code', blank=True),
        ),
    ]
