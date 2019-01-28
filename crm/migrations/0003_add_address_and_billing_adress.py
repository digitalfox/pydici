# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='billing_city',
            field=models.CharField(max_length=200, null=True, verbose_name='City', blank=True),
        ),
        migrations.AddField(
            model_name='company',
            name='billing_country',
            field=models.CharField(max_length=50, null=True, verbose_name='Country', blank=True),
        ),
        migrations.AddField(
            model_name='company',
            name='billing_street',
            field=models.TextField(null=True, verbose_name='Street', blank=True),
        ),
        migrations.AddField(
            model_name='company',
            name='billing_zipcode',
            field=models.CharField(max_length=30, null=True, verbose_name='Zip code', blank=True),
        ),
        migrations.AddField(
            model_name='company',
            name='city',
            field=models.CharField(max_length=200, null=True, verbose_name='City', blank=True),
        ),
        migrations.AddField(
            model_name='company',
            name='country',
            field=models.CharField(max_length=50, null=True, verbose_name='Country', blank=True),
        ),
        migrations.AddField(
            model_name='company',
            name='legal_description',
            field=models.TextField(null=True, verbose_name='Legal description', blank=True),
        ),
        migrations.AddField(
            model_name='company',
            name='street',
            field=models.TextField(null=True, verbose_name='Street', blank=True),
        ),
        migrations.AddField(
            model_name='company',
            name='zipcode',
            field=models.CharField(max_length=30, null=True, verbose_name='Zip code', blank=True),
        ),
        migrations.AddField(
            model_name='subsidiary',
            name='billing_city',
            field=models.CharField(max_length=200, null=True, verbose_name='City', blank=True),
        ),
        migrations.AddField(
            model_name='subsidiary',
            name='billing_country',
            field=models.CharField(max_length=50, null=True, verbose_name='Country', blank=True),
        ),
        migrations.AddField(
            model_name='subsidiary',
            name='billing_street',
            field=models.TextField(null=True, verbose_name='Street', blank=True),
        ),
        migrations.AddField(
            model_name='subsidiary',
            name='billing_zipcode',
            field=models.CharField(max_length=30, null=True, verbose_name='Zip code', blank=True),
        ),
        migrations.AddField(
            model_name='subsidiary',
            name='city',
            field=models.CharField(max_length=200, null=True, verbose_name='City', blank=True),
        ),
        migrations.AddField(
            model_name='subsidiary',
            name='country',
            field=models.CharField(max_length=50, null=True, verbose_name='Country', blank=True),
        ),
        migrations.AddField(
            model_name='subsidiary',
            name='legal_description',
            field=models.TextField(null=True, verbose_name='Legal description', blank=True),
        ),
        migrations.AddField(
            model_name='subsidiary',
            name='street',
            field=models.TextField(null=True, verbose_name='Street', blank=True),
        ),
        migrations.AddField(
            model_name='subsidiary',
            name='zipcode',
            field=models.CharField(max_length=30, null=True, verbose_name='Zip code', blank=True),
        ),
    ]
