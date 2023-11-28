# coding: utf-8

"""
Create test / demo data

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.core.management import BaseCommand

from crm.factories import SubsidiaryFactory

class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        for _ in range(3):
            SubsidiaryFactory()