# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Subsidiary'
        db.create_table(u'crm_subsidiary', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=200)),
            ('code', self.gf('django.db.models.fields.CharField')(unique=True, max_length=3)),
            ('web', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
        ))
        db.send_create_signal(u'crm', ['Subsidiary'])

        # Adding model 'Company'
        db.create_table(u'crm_company', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=200)),
            ('code', self.gf('django.db.models.fields.CharField')(unique=True, max_length=3)),
            ('web', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('businessOwner', self.gf('django.db.models.fields.related.ForeignKey')(related_name='company_business_owner', null=True, to=orm['people.Consultant'])),
        ))
        db.send_create_signal(u'crm', ['Company'])

        # Adding model 'ClientOrganisation'
        db.create_table(u'crm_clientorganisation', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('company', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Company'])),
        ))
        db.send_create_signal(u'crm', ['ClientOrganisation'])

        # Adding unique constraint on 'ClientOrganisation', fields ['name', 'company']
        db.create_unique(u'crm_clientorganisation', ['name', 'company_id'])

        # Adding model 'Contact'
        db.create_table(u'crm_contact', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=200)),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=75, blank=True)),
            ('phone', self.gf('django.db.models.fields.CharField')(max_length=30, blank=True)),
            ('mobile_phone', self.gf('django.db.models.fields.CharField')(max_length=30, blank=True)),
            ('fax', self.gf('django.db.models.fields.CharField')(max_length=30, blank=True)),
            ('function', self.gf('django.db.models.fields.CharField')(max_length=200, blank=True)),
        ))
        db.send_create_signal(u'crm', ['Contact'])

        # Adding M2M table for field contact_points on 'Contact'
        m2m_table_name = db.shorten_name(u'crm_contact_contact_points')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('contact', models.ForeignKey(orm[u'crm.contact'], null=False)),
            ('consultant', models.ForeignKey(orm[u'people.consultant'], null=False))
        ))
        db.create_unique(m2m_table_name, ['contact_id', 'consultant_id'])

        # Adding model 'BusinessBroker'
        db.create_table(u'crm_businessbroker', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('company', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Company'])),
            ('contact', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Contact'], null=True, on_delete=models.SET_NULL, blank=True)),
        ))
        db.send_create_signal(u'crm', ['BusinessBroker'])

        # Adding unique constraint on 'BusinessBroker', fields ['company', 'contact']
        db.create_unique(u'crm_businessbroker', ['company_id', 'contact_id'])

        # Adding model 'Supplier'
        db.create_table(u'crm_supplier', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('company', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Company'])),
            ('contact', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Contact'], null=True, on_delete=models.SET_NULL, blank=True)),
        ))
        db.send_create_signal(u'crm', ['Supplier'])

        # Adding unique constraint on 'Supplier', fields ['company', 'contact']
        db.create_unique(u'crm_supplier', ['company_id', 'contact_id'])

        # Adding model 'Client'
        db.create_table(u'crm_client', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('organisation', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.ClientOrganisation'])),
            ('contact', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Contact'], null=True, on_delete=models.SET_NULL, blank=True)),
            ('expectations', self.gf('django.db.models.fields.CharField')(default='3_FLAT', max_length=30)),
            ('alignment', self.gf('django.db.models.fields.CharField')(default='2_STANDARD', max_length=30)),
            ('active', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal(u'crm', ['Client'])

        # Adding unique constraint on 'Client', fields ['organisation', 'contact']
        db.create_unique(u'crm_client', ['organisation_id', 'contact_id'])

        # Adding model 'MissionContact'
        db.create_table(u'crm_missioncontact', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('company', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Company'])),
            ('contact', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Contact'])),
        ))
        db.send_create_signal(u'crm', ['MissionContact'])

        # Adding unique constraint on 'MissionContact', fields ['company', 'contact']
        db.create_unique(u'crm_missioncontact', ['company_id', 'contact_id'])

        # Adding model 'AdministrativeFunction'
        db.create_table(u'crm_administrativefunction', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=200)),
        ))
        db.send_create_signal(u'crm', ['AdministrativeFunction'])

        # Adding model 'AdministrativeContact'
        db.create_table(u'crm_administrativecontact', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('company', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Company'])),
            ('function', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.AdministrativeFunction'])),
            ('default_phone', self.gf('django.db.models.fields.CharField')(max_length=30, null=True, blank=True)),
            ('default_mail', self.gf('django.db.models.fields.EmailField')(max_length=100, null=True, blank=True)),
            ('default_fax', self.gf('django.db.models.fields.CharField')(max_length=100, null=True, blank=True)),
            ('contact', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['crm.Contact'], null=True, blank=True)),
        ))
        db.send_create_signal(u'crm', ['AdministrativeContact'])

        # Adding unique constraint on 'AdministrativeContact', fields ['company', 'contact']
        db.create_unique(u'crm_administrativecontact', ['company_id', 'contact_id'])


    def backwards(self, orm):
        # Removing unique constraint on 'AdministrativeContact', fields ['company', 'contact']
        db.delete_unique(u'crm_administrativecontact', ['company_id', 'contact_id'])

        # Removing unique constraint on 'MissionContact', fields ['company', 'contact']
        db.delete_unique(u'crm_missioncontact', ['company_id', 'contact_id'])

        # Removing unique constraint on 'Client', fields ['organisation', 'contact']
        db.delete_unique(u'crm_client', ['organisation_id', 'contact_id'])

        # Removing unique constraint on 'Supplier', fields ['company', 'contact']
        db.delete_unique(u'crm_supplier', ['company_id', 'contact_id'])

        # Removing unique constraint on 'BusinessBroker', fields ['company', 'contact']
        db.delete_unique(u'crm_businessbroker', ['company_id', 'contact_id'])

        # Removing unique constraint on 'ClientOrganisation', fields ['name', 'company']
        db.delete_unique(u'crm_clientorganisation', ['name', 'company_id'])

        # Deleting model 'Subsidiary'
        db.delete_table(u'crm_subsidiary')

        # Deleting model 'Company'
        db.delete_table(u'crm_company')

        # Deleting model 'ClientOrganisation'
        db.delete_table(u'crm_clientorganisation')

        # Deleting model 'Contact'
        db.delete_table(u'crm_contact')

        # Removing M2M table for field contact_points on 'Contact'
        db.delete_table(db.shorten_name(u'crm_contact_contact_points'))

        # Deleting model 'BusinessBroker'
        db.delete_table(u'crm_businessbroker')

        # Deleting model 'Supplier'
        db.delete_table(u'crm_supplier')

        # Deleting model 'Client'
        db.delete_table(u'crm_client')

        # Deleting model 'MissionContact'
        db.delete_table(u'crm_missioncontact')

        # Deleting model 'AdministrativeFunction'
        db.delete_table(u'crm_administrativefunction')

        # Deleting model 'AdministrativeContact'
        db.delete_table(u'crm_administrativecontact')


    models = {
        u'crm.administrativecontact': {
            'Meta': {'ordering': "('company', 'contact')", 'unique_together': "(('company', 'contact'),)", 'object_name': 'AdministrativeContact'},
            'company': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Company']"}),
            'contact': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Contact']", 'null': 'True', 'blank': 'True'}),
            'default_fax': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'default_mail': ('django.db.models.fields.EmailField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'default_phone': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True', 'blank': 'True'}),
            'function': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.AdministrativeFunction']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'crm.administrativefunction': {
            'Meta': {'ordering': "('name',)", 'object_name': 'AdministrativeFunction'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '200'})
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
        u'crm.supplier': {
            'Meta': {'ordering': "['company', 'contact']", 'unique_together': "(('company', 'contact'),)", 'object_name': 'Supplier'},
            'company': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Company']"}),
            'contact': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['crm.Contact']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
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
        }
    }

    complete_apps = ['crm']