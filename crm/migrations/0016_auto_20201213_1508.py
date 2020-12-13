# Generated by Django 2.2.13 on 2020-12-13 15:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0015_client_billing_lang'),
    ]

    operations = [
        migrations.AlterField(
            model_name='client',
            name='billing_lang',
            field=models.CharField(choices=[('fr-fr', 'French'), ('en-en', 'English')], default='fr-fr', max_length=10, verbose_name='Billing language'),
        ),
    ]
