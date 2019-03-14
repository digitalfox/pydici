# coding: utf-8
"""
Test cases for People module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.cache import cache

from crm.models import Subsidiary
from people.models import Consultant, ConsultantProfile, RateObjective
from staffing.models import Mission, Timesheet, FinancialCondition
from leads.models import Lead
from core.utils import nextMonth, previousMonth
from core.tests import PYDICI_FIXTURES, setup_test_user_features, TEST_USERNAME


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
        self.assertEqual(c.userTeam(), [User.objects.get(username="abr")])
        self.assertEqual(c.userTeam(excludeSelf=False), [User.objects.get(username="abr"), User.objects.get(username="sre")])

    def test_pending_action(self):
        c = Consultant.objects.get(trigramme="SRE")
        self.assertQuerysetEqual(c.pending_actions(), [])

    def test_turnover(self):
        current_month = date.today().replace(day=1)
        next_month = nextMonth(current_month)
        previous_month = previousMonth(current_month)
        lead = Lead.objects.get(id=1)
        c1 = Consultant.objects.get(id=1)
        c2 = Consultant.objects.get(id=2)
        mission = Mission(lead=lead, subsidiary_id=1, billing_mode="TIME_SPENT", nature="PROD", probability=100)
        mission.save()
        cache.clear()  # avoid bad computation due to rates cache with previous values
        # Add some timesheet - we fake with all charge on the first day
        Timesheet(mission=mission, working_date=previous_month, consultant=c1, charge=10).save()
        Timesheet(mission=mission, working_date=previous_month, consultant=c2, charge=5).save()
        Timesheet(mission=mission, working_date=current_month, consultant=c1, charge=10).save()
        Timesheet(mission=mission, working_date=current_month, consultant=c2, charge=5).save()
        # Add financial conditions for this mission
        FinancialCondition(consultant=c1, mission=mission, daily_rate=2000).save()
        FinancialCondition(consultant=c2, mission=mission, daily_rate=1000).save()
        done_work = (10 + 10) * 2000 + (5 + 5) * 1000
        # Define mission price
        mission.price = 40
        mission.billing_mode = "TIME_SPENT"
        mission.save()
        # In time spent, turnover is what we did
        self.assertEqual(c1.getTurnover(), 20*2000)
        mission.billing_mode = "FIXED_PRICE"
        mission.save()
        # In fixed price, turnover is limited by price in proportion of all work
        self.assertEqual(c1.getTurnover(), 20 * 2000 * mission.price * 1000 / done_work )
        self.assertEqual(c1.getTurnover() + c2.getTurnover(), mission.price * 1000)
        # Let add some margin by changing mission price.
        mission.price = 60
        mission.save()
        self.assertEqual(c1.getTurnover(), 20 * 2000) # like in time spent
        self.assertEqual(c1.getTurnover() + c2.getTurnover(), done_work )
        # Let archive mission to validate margin
        mission.active = False
        mission.save()
        self.assertEqual(c1.getTurnover(), 20 * 2000 * mission.price * 1000 / done_work)  # like in time spent
        self.assertEqual(c1.getTurnover() + c2.getTurnover(), mission.price * 1000)

