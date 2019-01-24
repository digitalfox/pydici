# coding: utf-8
"""
Test cases for People module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.test import TestCase
from django.core import urlresolvers
from django.contrib.auth.models import Group, User

from crm.models import Client, Subsidiary
from people.models import Consultant, ConsultantProfile
from staffing.models import Mission
from core.tests import PYDICI_FIXTURES, setup_test_user_features, TEST_USERNAME, TEST_PASSWORD


class PeopleModelTest(TestCase):
    fixtures = PYDICI_FIXTURES

    def test_people_consultant_save(self):
        c = Consultant()
        c.company = Subsidiary.objects.get(id=1)
        c.profil = ConsultantProfile.objects.get(id=1)
        c.name = "john doe"
        c.trigramme = "jdo"
        c.save()
        self.assertEqual(c.name, "John Doe")
        self.assertEqual(c.trigramme, "JDO")

    def test_people_consultant_active_missions(self):
        c = Consultant.objects.get(trigramme="SRE")
        self.assertEqual(list(c.active_missions()), list(Mission.objects.filter(id=1)))

    def test_getUser(self):
        c = Consultant.objects.get(trigramme="SRE")
        u = User.objects.get(username="sre")
        self.assertEqual(c.getUser(), u)
        c = Consultant.objects.get(trigramme="GBA")
        self.assertEqual(c.getUser(), None)

    def test_team(self):
        c = Consultant.objects.get(trigramme="SRE")
        self.assertEqual(list(c.team().order_by("id").values_list("id", flat=True)), [3, 5])
        self.assertEqual(list(c.team(excludeSelf=False).order_by("id").values_list("id", flat=True)), [1, 3, 5])
        self.assertEqual(list(c.team(excludeSelf=False, onlyActive=True).order_by("id").values_list("id", flat=True)), [1, 5])
        self.assertEqual(list(c.team(onlyActive=True).order_by("id").values_list("id", flat=True)), [5, ])

    def test_user_team(self):
        c = Consultant.objects.get(trigramme="SRE")
        self.assertEqual(c.userTeam(), [User.objects.get(username="abr"), None])
        self.assertEqual(c.userTeam(excludeSelf=False), [User.objects.get(username="abr"), None, User.objects.get(username="sre")])

    def test_pending_action(self):
        c = Consultant.objects.get(trigramme="SRE")
        self.assertQuerysetEqual(c.pending_actions(), [])
