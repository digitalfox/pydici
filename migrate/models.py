# coding:utf-8

from django.db import models

# Map models to old table structure
class OldBusinessBroker(models.Model):
    id = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=200, blank=True)
    email = models.CharField(max_length=75, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    mobile_phone = models.CharField(max_length=30, blank=True)
    fax = models.CharField(max_length=30, blank=True)
    company = models.CharField(max_length=200, blank=True)
    code = models.CharField(max_length=3, blank=True)
    contact_id = models.IntegerField(null=True, blank=True)
    company_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = u'crm_businessbroker_backup'
