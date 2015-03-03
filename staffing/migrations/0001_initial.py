# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Mission'
        db.create_table(u'staffing_mission', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('lead', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['leads.Lead'], null=True, blank=True)),
            ('deal_id', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=30, null=True, blank=True)),
            ('nature', self.gf('django.db.models.fields.CharField')(default='PROD', max_length=30)),
            ('billing_mode', self.gf('django.db.models.fields.CharField')(max_length=30, null=True)),
            ('active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('probability', self.gf('django.db.models.fields.IntegerField')(default=50)),
            ('price', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=10, decimal_places=3, blank=True)),
            ('update_date', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('subsidiary', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Subsidiary'])),
            ('archived_date', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('responsible', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='mission_responsible', null=True, to=orm['people.Consultant'])),
        ))
        db.send_create_signal(u'staffing', ['Mission'])

        # Adding M2M table for field contacts on 'Mission'
        m2m_table_name = db.shorten_name(u'staffing_mission_contacts')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('mission', models.ForeignKey(orm[u'staffing.mission'], null=False)),
            ('missioncontact', models.ForeignKey(orm[u'crm.missioncontact'], null=False))
        ))
        db.create_unique(m2m_table_name, ['mission_id', 'missioncontact_id'])

        # Adding model 'Holiday'
        db.create_table(u'staffing_holiday', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('day', self.gf('django.db.models.fields.DateField')()),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=200)),
        ))
        db.send_create_signal(u'staffing', ['Holiday'])

        # Adding model 'Staffing'
        db.create_table(u'staffing_staffing', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('consultant', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['people.Consultant'])),
            ('mission', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['staffing.Mission'])),
            ('staffing_date', self.gf('django.db.models.fields.DateField')()),
            ('charge', self.gf('django.db.models.fields.FloatField')(default=0)),
            ('comment', self.gf('django.db.models.fields.CharField')(max_length=500, null=True, blank=True)),
            ('update_date', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('last_user', self.gf('django.db.models.fields.CharField')(max_length=60, null=True, blank=True)),
        ))
        db.send_create_signal(u'staffing', ['Staffing'])

        # Adding unique constraint on 'Staffing', fields ['consultant', 'mission', 'staffing_date']
        db.create_unique(u'staffing_staffing', ['consultant_id', 'mission_id', 'staffing_date'])

        # Adding model 'Timesheet'
        db.create_table(u'staffing_timesheet', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('consultant', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['people.Consultant'])),
            ('mission', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['staffing.Mission'])),
            ('working_date', self.gf('django.db.models.fields.DateField')()),
            ('charge', self.gf('django.db.models.fields.FloatField')(default=0)),
        ))
        db.send_create_signal(u'staffing', ['Timesheet'])

        # Adding unique constraint on 'Timesheet', fields ['consultant', 'mission', 'working_date']
        db.create_unique(u'staffing_timesheet', ['consultant_id', 'mission_id', 'working_date'])

        # Adding model 'LunchTicket'
        db.create_table(u'staffing_lunchticket', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('consultant', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['people.Consultant'])),
            ('lunch_date', self.gf('django.db.models.fields.DateField')()),
            ('no_ticket', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'staffing', ['LunchTicket'])

        # Adding unique constraint on 'LunchTicket', fields ['consultant', 'lunch_date']
        db.create_unique(u'staffing_lunchticket', ['consultant_id', 'lunch_date'])

        # Adding model 'FinancialCondition'
        db.create_table(u'staffing_financialcondition', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('consultant', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['people.Consultant'])),
            ('mission', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['staffing.Mission'])),
            ('daily_rate', self.gf('django.db.models.fields.IntegerField')()),
            ('bought_daily_rate', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'staffing', ['FinancialCondition'])

        # Adding unique constraint on 'FinancialCondition', fields ['consultant', 'mission', 'daily_rate']
        db.create_unique(u'staffing_financialcondition', ['consultant_id', 'mission_id', 'daily_rate'])


    def backwards(self, orm):
        # Removing unique constraint on 'FinancialCondition', fields ['consultant', 'mission', 'daily_rate']
        db.delete_unique(u'staffing_financialcondition', ['consultant_id', 'mission_id', 'daily_rate'])

        # Removing unique constraint on 'LunchTicket', fields ['consultant', 'lunch_date']
        db.delete_unique(u'staffing_lunchticket', ['consultant_id', 'lunch_date'])

        # Removing unique constraint on 'Timesheet', fields ['consultant', 'mission', 'working_date']
        db.delete_unique(u'staffing_timesheet', ['consultant_id', 'mission_id', 'working_date'])

        # Removing unique constraint on 'Staffing', fields ['consultant', 'mission', 'staffing_date']
        db.delete_unique(u'staffing_staffing', ['consultant_id', 'mission_id', 'staffing_date'])

        # Deleting model 'Mission'
        db.delete_table(u'staffing_mission')

        # Removing M2M table for field contacts on 'Mission'
        db.delete_table(db.shorten_name(u'staffing_mission_contacts'))

        # Deleting model 'Holiday'
        db.delete_table(u'staffing_holiday')

        # Deleting model 'Staffing'
        db.delete_table(u'staffing_staffing')

        # Deleting model 'Timesheet'
        db.delete_table(u'staffing_timesheet')

        # Deleting model 'LunchTicket'
        db.delete_table(u'staffing_lunchticket')

        # Deleting model 'FinancialCondition'
        db.delete_table(u'staffing_financialcondition')


    models = {
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'crm.businessbroker': {
            'Meta': {'ordering': "['company', 'contact']", 'unique_together': "(('company', 'contact'),)", 'object_name': 'BusinessBroker'},
            'company': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Company']"}),
            'contact': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Contact']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'crm.client': {
            'Meta': {'ordering': "['organisation', 'contact']", 'unique_together': "(('organisation', 'contact'),)", 'object_name': 'Client'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'alignment': ('django.db.models.fields.CharField', [], {'default': "'2_STANDARD'", 'max_length': '30'}),
            'contact': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Contact']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'expectations': ('django.db.models.fields.CharField', [], {'default': "'3_FLAT'", 'max_length': '30'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'organisation': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.ClientOrganisation']"})
        },
        u'crm.clientorganisation': {
            'Meta': {'ordering': "['company', 'name']", 'unique_together': "(('name', 'company'),)", 'object_name': 'ClientOrganisation'},
            'company': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Company']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        u'crm.company': {
            'Meta': {'ordering': "['name']", 'object_name': 'Company'},
            'businessOwner': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'company_business_owner'", 'null': 'True', 'to': u"orm['people.Consultant']"}),
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '3'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '200'}),
            'web': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        u'crm.contact': {
            'Meta': {'ordering': "['name']", 'object_name': 'Contact'},
            'contact_points': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['people.Consultant']", 'symmetrical': 'False', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'fax': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'function': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mobile_phone': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '200'}),
            'phone': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'})
        },
        u'crm.missioncontact': {
            'Meta': {'ordering': "['company', 'contact']", 'unique_together': "(('company', 'contact'),)", 'object_name': 'MissionContact'},
            'company': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Company']"}),
            'contact': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Contact']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'crm.subsidiary': {
            'Meta': {'ordering': "['name']", 'object_name': 'Subsidiary'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '3'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '200'}),
            'web': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        u'leads.lead': {
            'Meta': {'ordering': "['client__organisation__company__name', 'name']", 'object_name': 'Lead'},
            'action': ('django.db.models.fields.CharField', [], {'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'business_broker': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'lead_broker'", 'null': 'True', 'to': u"orm['crm.BusinessBroker']"}),
            'client': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Client']"}),
            'client_deal_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'creation_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 3, 3, 0, 0)'}),
            'deal_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '100', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'due_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'external_staffing': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'paying_authority': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'lead_paying'", 'null': 'True', 'to': u"orm['crm.BusinessBroker']"}),
            'responsible': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'lead_responsible'", 'null': 'True', 'to': u"orm['people.Consultant']"}),
            'sales': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '3', 'blank': 'True'}),
            'salesman': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['people.SalesMan']", 'null': 'True', 'blank': 'True'}),
            'send_email': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'staffing': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['people.Consultant']", 'symmetrical': 'False', 'blank': 'True'}),
            'start_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'QUALIF'", 'max_length': '30', 'db_index': 'True'}),
            'subsidiary': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Subsidiary']"}),
            'update_date': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
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
        u'people.salesman': {
            'Meta': {'ordering': "['name']", 'object_name': 'SalesMan'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'company': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Subsidiary']"}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'phone': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'trigramme': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '4'})
        },
        u'staffing.financialcondition': {
            'Meta': {'unique_together': "(('consultant', 'mission', 'daily_rate'),)", 'object_name': 'FinancialCondition'},
            'bought_daily_rate': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'consultant': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['people.Consultant']"}),
            'daily_rate': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mission': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['staffing.Mission']"})
        },
        u'staffing.holiday': {
            'Meta': {'object_name': 'Holiday'},
            'day': ('django.db.models.fields.DateField', [], {}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'staffing.lunchticket': {
            'Meta': {'unique_together': "(('consultant', 'lunch_date'),)", 'object_name': 'LunchTicket'},
            'consultant': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['people.Consultant']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lunch_date': ('django.db.models.fields.DateField', [], {}),
            'no_ticket': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'staffing.mission': {
            'Meta': {'ordering': "['nature', 'lead__client__organisation__company', 'id', 'description']", 'object_name': 'Mission'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'archived_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'billing_mode': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'contacts': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['crm.MissionContact']", 'symmetrical': 'False', 'blank': 'True'}),
            'deal_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lead': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['leads.Lead']", 'null': 'True', 'blank': 'True'}),
            'nature': ('django.db.models.fields.CharField', [], {'default': "'PROD'", 'max_length': '30'}),
            'price': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '3', 'blank': 'True'}),
            'probability': ('django.db.models.fields.IntegerField', [], {'default': '50'}),
            'responsible': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'mission_responsible'", 'null': 'True', 'to': u"orm['people.Consultant']"}),
            'subsidiary': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Subsidiary']"}),
            'update_date': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        },
        u'staffing.staffing': {
            'Meta': {'ordering': "['staffing_date', 'consultant']", 'unique_together': "(('consultant', 'mission', 'staffing_date'),)", 'object_name': 'Staffing'},
            'charge': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'comment': ('django.db.models.fields.CharField', [], {'max_length': '500', 'null': 'True', 'blank': 'True'}),
            'consultant': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['people.Consultant']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_user': ('django.db.models.fields.CharField', [], {'max_length': '60', 'null': 'True', 'blank': 'True'}),
            'mission': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['staffing.Mission']"}),
            'staffing_date': ('django.db.models.fields.DateField', [], {}),
            'update_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        u'staffing.timesheet': {
            'Meta': {'ordering': "['working_date', 'consultant']", 'unique_together': "(('consultant', 'mission', 'working_date'),)", 'object_name': 'Timesheet'},
            'charge': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'consultant': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['people.Consultant']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mission': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['staffing.Mission']"}),
            'working_date': ('django.db.models.fields.DateField', [], {})
        },
        u'taggit.tag': {
            'Meta': {'object_name': 'Tag'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'slug': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '100'})
        },
        u'taggit.taggeditem': {
            'Meta': {'object_name': 'TaggedItem'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'taggit_taggeditem_tagged_items'", 'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'object_id': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'tag': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'taggit_taggeditem_items'", 'to': u"orm['taggit.Tag']"})
        }
    }

    complete_apps = ['staffing']