import os

from django.test import TestCase

from batch.incwo import core
from crm.models import Company, Contact


TEST_DIR = os.path.join(os.path.dirname(__file__), 'test-data')


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
