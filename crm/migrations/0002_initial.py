# -*- coding: utf-8 -*-


from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=200, verbose_name='Name')),
                ('code', models.CharField(unique=True, max_length=3, verbose_name='Code')),
                ('web', models.URLField(null=True, blank=True)),
                ('external_id', models.CharField(default=None, max_length=200, unique=True, null=True, blank=True)),
                ('businessOwner', models.ForeignKey(related_name='company_business_owner', verbose_name='Business owner', to='people.Consultant', null=True, on_delete=models.SET_NULL)),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'Company',
                'verbose_name_plural': 'Companies',
            },
        ),
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200, verbose_name='Name')),
                ('email', models.EmailField(max_length=254, blank=True)),
                ('phone', models.CharField(max_length=30, verbose_name='Phone', blank=True)),
                ('mobile_phone', models.CharField(max_length=30, verbose_name='Mobile phone', blank=True)),
                ('fax', models.CharField(max_length=30, verbose_name='Fax', blank=True)),
                ('function', models.CharField(max_length=200, verbose_name='Function', blank=True)),
                ('external_id', models.CharField(default=None, max_length=200, unique=True, null=True, blank=True)),
                ('contact_points', models.ManyToManyField(to='people.Consultant', verbose_name='Points of contact', blank=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='AdministrativeContact',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('default_phone', models.CharField(max_length=30, null=True, verbose_name='Phone Switchboard', blank=True)),
                ('default_mail', models.EmailField(max_length=100, null=True, verbose_name='Generic email', blank=True)),
                ('default_fax', models.CharField(max_length=100, null=True, verbose_name='Generic fax', blank=True)),
            ],
            options={
                'ordering': ('company', 'contact'),
                'verbose_name': 'Administrative contact',
            },
        ),
        migrations.CreateModel(
            name='AdministrativeFunction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=200, verbose_name='Name')),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='BusinessBroker',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
            ],
            options={
                'ordering': ['company', 'contact'],
                'verbose_name': 'Business broker',
            },
        ),
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('expectations', models.CharField(default='3_FLAT', max_length=30, verbose_name='Expectations', choices=[('1_NONE', 'Aucun(e)'), ('2_DECREASING', 'D\xe9croissance'), ('3_FLAT', 'Inchang\xe9e'), ('4_INCREASING', 'Croissance')])),
                ('alignment', models.CharField(default='2_STANDARD', max_length=30, verbose_name='Strategic alignment', choices=[('1_RESTRAIN', '\xc0 restreindre'), ('2_STANDARD', 'Standard'), ('3_STRATEGIC', 'Strat\xe9gique')])),
                ('active', models.BooleanField(default=True, verbose_name='Active')),
            ],
            options={
                'ordering': ['organisation', 'contact'],
                'verbose_name': 'Client',
            },
        ),
        migrations.CreateModel(
            name='ClientOrganisation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200, verbose_name='Organization')),
            ],
            options={
                'ordering': ['company', 'name'],
                'verbose_name': 'Client organisation',
            },
        ),
        migrations.CreateModel(
            name='MissionContact',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('company', models.ForeignKey(verbose_name='company', to='crm.Company', on_delete=models.CASCADE)),
                ('contact', models.ForeignKey(verbose_name='Contact', to='crm.Contact', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['company', 'contact'],
                'verbose_name': 'Mission contact',
            },
        ),
        migrations.CreateModel(
            name='Supplier',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('company', models.ForeignKey(verbose_name='Supplier company', to='crm.Company', on_delete=models.CASCADE)),
                ('contact', models.ForeignKey(on_delete=models.SET_NULL, verbose_name='Contact', blank=True, to='crm.Contact', null=True)),
            ],
            options={
                'ordering': ['company', 'contact'],
                'verbose_name': 'Supplier',
            },
        ),
        migrations.AddField(
            model_name='clientorganisation',
            name='company',
            field=models.ForeignKey(verbose_name='Client company', to='crm.Company', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='client',
            name='contact',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, verbose_name='Contact', blank=True, to='crm.Contact', null=True),
        ),
        migrations.AddField(
            model_name='client',
            name='organisation',
            field=models.ForeignKey(verbose_name='Company : Organisation', to='crm.ClientOrganisation', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='businessbroker',
            name='company',
            field=models.ForeignKey(verbose_name='Broker company', to='crm.Company', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='businessbroker',
            name='contact',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, verbose_name='Contact', blank=True, to='crm.Contact', null=True),
        ),
        migrations.AddField(
            model_name='administrativecontact',
            name='company',
            field=models.ForeignKey(verbose_name='company', to='crm.Company', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='administrativecontact',
            name='contact',
            field=models.ForeignKey(verbose_name='Contact', blank=True, to='crm.Contact', null=True, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='administrativecontact',
            name='function',
            field=models.ForeignKey(verbose_name='Function', to='crm.AdministrativeFunction', on_delete=models.CASCADE),
        ),
        migrations.AlterUniqueTogether(
            name='supplier',
            unique_together=set([('company', 'contact')]),
        ),
        migrations.AlterUniqueTogether(
            name='missioncontact',
            unique_together=set([('company', 'contact')]),
        ),
        migrations.AlterUniqueTogether(
            name='clientorganisation',
            unique_together=set([('name', 'company')]),
        ),
        migrations.AlterUniqueTogether(
            name='client',
            unique_together=set([('organisation', 'contact')]),
        ),
        migrations.AlterUniqueTogether(
            name='businessbroker',
            unique_together=set([('company', 'contact')]),
        ),
        migrations.AlterUniqueTogether(
            name='administrativecontact',
            unique_together=set([('company', 'contact')]),
        ),
    ]
