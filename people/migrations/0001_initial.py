# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'ConsultantProfile'
        db.create_table(u'people_consultantprofile', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=50)),
            ('level', self.gf('django.db.models.fields.IntegerField')()),
        ))
        db.send_create_signal(u'people', ['ConsultantProfile'])

        # Adding model 'Consultant'
        db.create_table(u'people_consultant', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('trigramme', self.gf('django.db.models.fields.CharField')(unique=True, max_length=4)),
            ('company', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Subsidiary'])),
            ('productive', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('manager', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['people.Consultant'], null=True, blank=True)),
            ('profil', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['people.ConsultantProfile'])),
            ('subcontractor', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('subcontractor_company', self.gf('django.db.models.fields.CharField')(max_length=200, null=True, blank=True)),
        ))
        db.send_create_signal(u'people', ['Consultant'])

        # Adding model 'RateObjective'
        db.create_table(u'people_rateobjective', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('consultant', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['people.Consultant'])),
            ('start_date', self.gf('django.db.models.fields.DateField')()),
            ('daily_rate', self.gf('django.db.models.fields.IntegerField')()),
        ))
        db.send_create_signal(u'people', ['RateObjective'])

        # Adding model 'SalesMan'
        db.create_table(u'people_salesman', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('trigramme', self.gf('django.db.models.fields.CharField')(unique=True, max_length=4)),
            ('company', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Subsidiary'])),
            ('active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=75, blank=True)),
            ('phone', self.gf('django.db.models.fields.CharField')(max_length=30, blank=True)),
        ))
        db.send_create_signal(u'people', ['SalesMan'])


    def backwards(self, orm):
        # Deleting model 'ConsultantProfile'
        db.delete_table(u'people_consultantprofile')

        # Deleting model 'Consultant'
        db.delete_table(u'people_consultant')

        # Deleting model 'RateObjective'
        db.delete_table(u'people_rateobjective')

        # Deleting model 'SalesMan'
        db.delete_table(u'people_salesman')


    models = {
        u'crm.subsidiary': {
            'Meta': {'ordering': "['name']", 'object_name': 'Subsidiary'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '3'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '200'}),
            'web': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        u'people.consultant': {
            'Meta': {'ordering': "['name']", 'object_name': 'Consultant'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'company': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Subsidiary']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'manager': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['people.Consultant']", 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'productive': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'profil': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['people.ConsultantProfile']"}),
            'subcontractor': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'subcontractor_company': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'trigramme': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '4'})
        },
        u'people.consultantprofile': {
            'Meta': {'ordering': "['level']", 'object_name': 'ConsultantProfile'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.IntegerField', [], {}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50'})
        },
        u'people.rateobjective': {
            'Meta': {'object_name': 'RateObjective'},
            'consultant': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['people.Consultant']"}),
            'daily_rate': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'start_date': ('django.db.models.fields.DateField', [], {})
        },
        u'people.salesman': {
            'Meta': {'ordering': "['name']", 'object_name': 'SalesMan'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'company': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Subsidiary']"}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'phone': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'trigramme': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '4'})
        }
    }

    complete_apps = ['people']