# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Lead'
        db.create_table(u'leads_lead', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('description', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('action', self.gf('django.db.models.fields.CharField')(max_length=2000, null=True, blank=True)),
            ('sales', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=10, decimal_places=3, blank=True)),
            ('salesman', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['people.SalesMan'], null=True, blank=True)),
            ('external_staffing', self.gf('django.db.models.fields.CharField')(max_length=300, blank=True)),
            ('responsible', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='lead_responsible', null=True, to=orm['people.Consultant'])),
            ('business_broker', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='lead_broker', null=True, to=orm['crm.BusinessBroker'])),
            ('paying_authority', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='lead_paying', null=True, to=orm['crm.BusinessBroker'])),
            ('start_date', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('due_date', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('state', self.gf('django.db.models.fields.CharField')(default='QUALIF', max_length=30, db_index=True)),
            ('client', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Client'])),
            ('creation_date', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 3, 3, 0, 0))),
            ('deal_id', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=100, blank=True)),
            ('client_deal_id', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('update_date', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('send_email', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('subsidiary', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Subsidiary'])),
        ))
        db.send_create_signal(u'leads', ['Lead'])

        # Adding M2M table for field staffing on 'Lead'
        m2m_table_name = db.shorten_name(u'leads_lead_staffing')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('lead', models.ForeignKey(orm[u'leads.lead'], null=False)),
            ('consultant', models.ForeignKey(orm[u'people.consultant'], null=False))
        ))
        db.create_unique(m2m_table_name, ['lead_id', 'consultant_id'])


    def backwards(self, orm):
        # Deleting model 'Lead'
        db.delete_table(u'leads_lead')

        # Removing M2M table for field staffing on 'Lead'
        db.delete_table(db.shorten_name(u'leads_lead_staffing'))


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

    complete_apps = ['leads']