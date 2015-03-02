import os

from django.test import TestCase

from batch.incwo import core
from crm.models import Company


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
