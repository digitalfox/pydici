# -*- coding: utf-8 -*-


from django.db import models, migrations
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0002_initial'),
        ('taggit', '0001_initial'),
        ('people', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='Lead',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200, verbose_name='Name')),
                ('description', models.TextField(blank=True)),
                ('action', models.CharField(max_length=2000, null=True, verbose_name='Action', blank=True)),
                ('sales', models.DecimalField(null=True, verbose_name='Price (k\u20ac)', max_digits=10, decimal_places=3, blank=True)),
                ('external_staffing', models.CharField(max_length=300, verbose_name='External staffing', blank=True)),
                ('start_date', models.DateField(null=True, verbose_name='Starting', blank=True)),
                ('due_date', models.DateField(null=True, verbose_name='Due', blank=True)),
                ('state', models.CharField(default='QUALIF', max_length=30, verbose_name='State', db_index=True, choices=[('QUALIF', 'En qualif.'), ('WRITE_OFFER', 'Propal. \xe0 \xe9crire'), ('OFFER_SENT', 'Propal. envoy\xe9e'), ('NEGOTIATION', 'En n\xe9go.'), ('WON', 'Gagn\xe9e'), ('LOST', 'Perdue'), ('FORGIVEN', 'Abandonn\xe9e'), ('SLEEPING', 'En sommeil')])),
                ('creation_date', models.DateTimeField(auto_now_add=True, verbose_name='Creation')),
                ('deal_id', models.CharField(db_index=True, max_length=100, verbose_name='Deal id', blank=True)),
                ('client_deal_id', models.CharField(max_length=100, verbose_name='Client deal id', blank=True)),
                ('update_date', models.DateTimeField(auto_now=True, verbose_name='Updated')),
                ('send_email', models.BooleanField(default=True, verbose_name='Send lead by email')),
                ('external_id', models.CharField(default=None, max_length=200, unique=True, null=True, blank=True)),
                ('business_broker', models.ForeignKey(related_name='lead_broker', verbose_name='Business broker', blank=True, to='crm.BusinessBroker', null=True, on_delete=models.SET_NULL)),
                ('client', models.ForeignKey(verbose_name='Client', to='crm.Client', on_delete=models.CASCADE)),
                ('paying_authority', models.ForeignKey(related_name='lead_paying', verbose_name='Paying authority', blank=True, to='crm.BusinessBroker', null=True, on_delete=models.SET_NULL)),
                ('responsible', models.ForeignKey(related_name='lead_responsible', verbose_name='Responsible', blank=True, to='people.Consultant', null=True, on_delete=models.SET_NULL)),
                ('salesman', models.ForeignKey(verbose_name='Salesman', blank=True, to='people.SalesMan', null=True, on_delete=models.SET_NULL)),
                ('staffing', models.ManyToManyField(to='people.Consultant', blank=True)),
                ('subsidiary', models.ForeignKey(verbose_name='Subsidiary', to='crm.Subsidiary', on_delete=models.CASCADE)),
                ('tags', taggit.managers.TaggableManager(to='taggit.Tag', through='taggit.TaggedItem', blank=True, help_text='A comma-separated list of tags.', verbose_name='Tags')),
            ],
            options={
                'ordering': ['client__organisation__company__name', 'name'],
                'verbose_name': 'Lead',
            },
        ),
        migrations.CreateModel(
            name='StateProba',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('state', models.CharField(max_length=30, verbose_name='State', choices=[('QUALIF', 'En qualif.'), ('WRITE_OFFER', 'Propal. \xe0 \xe9crire'), ('OFFER_SENT', 'Propal. envoy\xe9e'), ('NEGOTIATION', 'En n\xe9go.'), ('WON', 'Gagn\xe9e'), ('LOST', 'Perdue'), ('FORGIVEN', 'Abandonn\xe9e'), ('SLEEPING', 'En sommeil')])),
                ('score', models.IntegerField(verbose_name='Score')),
                ('lead', models.ForeignKey(to='leads.Lead', on_delete=models.CASCADE)),
            ],
        ),
    ]
