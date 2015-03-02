import os

from unittest import skip

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
        lst = core.load_objects(os.path.join(TEST_DIR, 'contacts'), 'firms')
        core.import_firms(lst)
        lst = core.load_objects(os.path.join(TEST_DIR, 'contacts'), 'contacts')
        core.import_contacts(lst)

        company = Company.objects.get(pk=1)
        contact = Contact.objects.get(pk=12)

        company_contacts = Contact.objects.filter(missioncontact__company=company)
        self.assertEquals(list(company_contacts), [contact])

        # Import twice to check for conflicts
        core.import_contacts(lst)

    @skip('Contact.name is unique right now')
    def test_import_homonyms(self):
        lst = core.load_objects(os.path.join(TEST_DIR, 'homonyms'), 'firms')
        core.import_firms(lst)
        lst = core.load_objects(os.path.join(TEST_DIR, 'homonyms'), 'contacts')
        core.import_contacts(lst)

        contact_lst = Contact.objects.filter(name='John Doe')
        self.assertEquals(len(contact_lst), 2)
