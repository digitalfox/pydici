# Generated by Django 3.2.16 on 2022-12-10 18:00

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def forwards(apps, schema_editor):
    Client = apps.get_model("crm", "Client")
    for client in Client.objects.all():
        client.organisation.billing_name = client.billing_name
        client.organisation.save()

    for client in Client.objects.exclude(billing_lang=settings.LANGUAGE_CODE):
        client.organisation.billing_lang = client.billing_lang
        client.organisation.save()


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0019_remove_client_vat_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientorganisation',
            name='billing_contact',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='crm.administrativecontact', verbose_name='Billing contact'),
        ),
        migrations.AddField(
            model_name='clientorganisation',
            name='billing_lang',
            field=models.CharField(choices=[('fr-fr', 'French'), ('en-en', 'English')], default='fr-fr', max_length=10, verbose_name='Billing language'),
        ),
        migrations.AddField(
            model_name='clientorganisation',
            name='billing_name',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Name used for billing'),
        ),
        migrations.RunPython(forwards),
        migrations.RemoveField(
            model_name='client',
            name='billing_contact',
        ),
        migrations.RemoveField(
            model_name='client',
            name='billing_lang',
        ),
        migrations.RemoveField(
            model_name='client',
            name='billing_name',
        ),
    ]
