# -*- coding: utf-8 -*-


from django.db import migrations, models

def add_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    Parameter.objects.bulk_create([
        Parameter(key="HOST", value="http://localhost:8888", type="TEXT",
                  desc="Host base URL (without any prefix and trailing slash) used for absolute link. Used in email. Ex. http://www.my-site.com or http://localhost:8080"),
        Parameter(key="MAIL_FROM ", value="sebastien.renard@digitalfox.org", type="TEXT",
                  desc="Default email address used when sending mails"),
        Parameter(key="LEAD_MAIL_TO", value="sebastien.renard@digitalfox.org", type="TEXT",
                  desc="Email address used to send new / updated leads"),
        Parameter(key="HELP_PAGE", value="/my_custom_help_page.html", type="TEXT",
                  desc="Link to your custom help page. May be absolute or relative"),
    ])


def remove_default_parameters(apps, schema_editor):
    Parameter = apps.get_model("core", "Parameter")
    Parameter.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Parameter',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('key', models.CharField(unique=True, max_length=255, verbose_name='Key')),
                ('value', models.CharField(max_length=255, verbose_name='Value')),
                ('type', models.CharField(max_length=30, verbose_name='Type', choices=[('TEXT', 'text'), ('FLOAT', 'float')])),
                ('desc', models.CharField(max_length=255, verbose_name='Description')),
            ],
        ),
        migrations.RunPython(add_default_parameters, remove_default_parameters),
    ]
