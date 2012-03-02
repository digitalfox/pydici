#!/usr/bin/env python

# Convert business brokers to new CRM2 structure
# Need previous execution of migrate_new_crm.sql

import sys
from os.path import abspath, join, pardir, dirname
sys.path.append(abspath(join(dirname(__file__), pardir)))
import settings

settings.INSTALLED_APPS.append("migrate")

from django.core.management import setup_environ
if __name__ == "__main__":
    setup_environ(settings)
    from migrate.models import OldBusinessBroker
    from crm.models import Contact, Company, BusinessBroker
    for broker in OldBusinessBroker.objects.all():
        # Look if a contact with that name already exist
        contact, created = Contact.objects.get_or_create(name=broker.name)
        if created:
            print "Create contact %s" % broker.name
            contact.email = broker.email
            contact.phone = broker.phone
            contact.mobile_phone = broker.mobile_phone
            contact.fax = broker.fax
            contact.save()
        # Look if company of old broker exist
        company, created = Company.objects.get_or_create(name=broker.company, defaults={"code":broker.code})
        if created:
            print "Create company %s" % broker.company
        # Create new business broker with previous PK and previous values
        newBroker = BusinessBroker.objects.create(contact=contact, company=company, id=broker.id)
        newBroker.save()
