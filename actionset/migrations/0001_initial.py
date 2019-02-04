# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('description', models.TextField(verbose_name='Description', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='ActionSet',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=50, verbose_name='Name')),
                ('description', models.TextField(verbose_name='Description', blank=True)),
                ('trigger', models.CharField(blank=True, max_length=50, null=True, verbose_name='Trigger', choices=[('NEW_LEAD', 'Quand une affaire est créée'), ('WON_LEAD', 'Quand une affaire est gagnée'), ('NEW_MISSION', 'Quand une mission est créée'), ('ARCHIVED_MISSION', 'Quand une mission est archivée'), ('NEW_CONSULTANT', 'Quand un consultant est créé')])),
                ('active', models.BooleanField(default=True, verbose_name='Active')),
            ],
        ),
        migrations.CreateModel(
            name='ActionState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('state', models.CharField(default='TO_BE_DONE', max_length=50, verbose_name='State', db_index=True, choices=[('TO_BE_DONE', 'To be done'), ('DONE', 'Done'), ('NA', 'N/A')])),
                ('creation_date', models.DateTimeField(auto_now_add=True, verbose_name='Creation')),
                ('update_date', models.DateTimeField(auto_now=True, verbose_name='Updated')),
                ('target_id', models.PositiveIntegerField(null=True, verbose_name='Content id', blank=True)),
                ('action', models.ForeignKey(to='actionset.Action', on_delete=models.deletion.CASCADE)),
                ('target_type', models.ForeignKey(verbose_name='Target content type', blank=True, to='contenttypes.ContentType', null=True, on_delete=models.deletion.CASCADE,)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.deletion.CASCADE)),
            ],
        ),
        migrations.AddField(
            model_name='action',
            name='actionset',
            field=models.ForeignKey(to='actionset.ActionSet', on_delete=models.deletion.CASCADE),
        ),
    ]
