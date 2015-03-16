# encoding: utf-8
import logging
import os
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from batch.incwo import core
from crm.models import Client, Company, Contact, Subsidiary
from leads.models import Lead


TEST_DIR = os.path.join(os.path.dirname(__file__), 'test-data')


def load_and_import_objects(base_dir, context):
    for sub_dir in core.SUB_DIRS:
        object_dir = os.path.join(base_dir, sub_dir)
        if not os.path.exists(object_dir):
            continue
        lst = core.load_objects(base_dir, sub_dir)
        import_method = getattr(core, 'import_' + sub_dir)
        import_method(lst, context)


class FirmImportTest(TestCase):
    def test_duplicate_firms(self):
        lst = core.load_objects(os.path.join(TEST_DIR, 'duplicate-firms'), '.')
        nb_objects = len(lst)
        core.import_firms(lst)
        self.assertEquals(len(Company.objects.all()), nb_objects)

    def test_import_firms_twice(self):
        lst = core.load_objects(os.path.join(TEST_DIR, 'import-twice'), '.')
        nb_objects = len(lst)
        core.import_firms(lst)
        self.assertEquals(len(Company.objects.all()), nb_objects)
        core.import_firms(lst)
        self.assertEquals(len(Company.objects.all()), nb_objects)


class ContactImportTest(TestCase):
    def test_import_contact(self):
        firm_lst = core.load_objects(os.path.join(TEST_DIR, 'contacts'), 'firms')
        core.import_firms(firm_lst)
        contact_lst = core.load_objects(os.path.join(TEST_DIR, 'contacts'), 'contacts')
        core.import_contacts(contact_lst)

        company = Company.objects.get(pk=1)
        classic_contact = Contact.objects.get(pk=12)
        jobless_contact = Contact.objects.get(pk=34)

        company_contacts = Contact.objects.filter(client__organisation__company=company)
        self.assertItemsEqual(company_contacts, [classic_contact, jobless_contact])

        # Import twice to check for conflicts
        core.import_firms(firm_lst)
        core.import_contacts(contact_lst)

    def test_import_homonyms(self):
        lst = core.load_objects(os.path.join(TEST_DIR, 'homonyms'), 'firms')
        core.import_firms(lst)
        lst = core.load_objects(os.path.join(TEST_DIR, 'homonyms'), 'contacts')
        core.import_contacts(lst)

        contact_lst = Contact.objects.filter(name='John Doe')
        self.assertEquals(len(contact_lst), 2)

    def test_import_contact_items(self):
        contact_lst = core.load_objects(os.path.join(TEST_DIR, 'contact-items'), '.')
        core.import_contacts(contact_lst)

        contact = Contact.objects.get(pk=12)
        self.assertEquals(contact.email, 'valerie.rame@acme.com')
        self.assertEquals(contact.phone, '01 23 45 67 89')
        self.assertEquals(contact.mobile_phone, '06 78 90 12 34')
        self.assertEquals(contact.fax, '01 23 45 67 01')


class ProposalSheetImportTest(TestCase):
    def setUp(self):
        self.subsidiary = Subsidiary(name='test', code='t')
        self.subsidiary.save()

        # Lead.post_save needs a superuser, let's create one
        user = User.objects.create_user(username='admin')
        user.is_superuser = True
        user.save()

        # Silence logger
        core.logger.addHandler(logging.NullHandler())

    def test_import_proposal_sheets(self):
        context = core.ImportContext(subsidiary=self.subsidiary)
        firm_lst = core.load_objects(os.path.join(TEST_DIR, 'proposals'), 'firms')
        core.import_firms(firm_lst)
        contact_lst = core.load_objects(os.path.join(TEST_DIR, 'proposals'), 'contacts')
        core.import_contacts(contact_lst)
        proposal_sheet_lst = core.load_objects(os.path.join(TEST_DIR, 'proposals'), 'proposal_sheets')
        core.import_proposal_sheets(proposal_sheet_lst, context)

        # Check lead 3, linked to a firm
        lead = Lead.objects.get(pk=3)
        self.assertEquals(lead.state, 'WON')
        self.assertEquals(lead.deal_id, 'D1234-56789')
        self.assertEquals(lead.name, 'Project Foobar')
        self.assertEquals(lead.description, 'Echo Alpha Tango')

        client = Client.objects.get(organisation__company_id=1, contact=None)
        self.assertEquals(lead.client, client)

        # Check lead 4, linked to a contact
        lead = Lead.objects.get(pk=4)
        self.assertEquals(lead.state, 'WON')
        self.assertEquals(lead.deal_id, 'D5678-90123')
        self.assertEquals(lead.name, 'No Firm ID Proposal')

        client = Client.objects.get(contact_id=12)
        self.assertEquals(lead.client, client)

        # No lead 5, because it was lost
        self.assertFalse(Lead.objects.filter(pk=5))

    def test_import_proposal_lines(self):
        context = core.ImportContext(subsidiary=self.subsidiary,
                                     import_missions=True)
        load_and_import_objects(os.path.join(TEST_DIR, 'proposal-lines'), context)

        lead = Lead.objects.get(pk=3)
        EXPECTED_DESCRIPTION = \
u"""Echo Alpha Tango
*Engineering*
- Dev. Dev Foobar. 3 M/D × 500 € = 1500 €
- Dev _[option]_. Implement remote control. 2 M/D × 450 € = 900 €
Total: 2400 €
"""

        self.assertEquals(lead.sales, Decimal('1.5'))

        # There should be one associated mission
        missions = lead.mission_set.all()
        self.assertEquals(len(missions), 1)
        mission = missions[0]
        self.assertEquals(mission.price, Decimal('1.5'))
