# coding: utf-8
"""
Test cases
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

# Python/Django test modules
from django.test import TestCase
from django.core import urlresolvers
from django.contrib.auth.models import User

# Third party modules
import workflows.utils as wf
import permissions.utils as perm
from workflows.models import Transition

# Pydici modules
from core.utils import monthWeekNumber, previousWeek, nextWeek
from leads.models import Lead
from people.models import Consultant, ConsultantProfile
from crm.models import Client, Subsidiary, BusinessBroker
from staffing.models import Mission
from expense.models import Expense, ExpenseCategory, ExpensePayment
from expense.default_workflows import install_expense_workflow
import pydici.settings

# Python modules used by tests
from urllib2 import urlparse
from datetime import date
import os
from decimal import Decimal

TEST_USERNAME = "sre"
TEST_PASSWORD = "sre"
PREFIX = "/" + pydici.settings.PYDICI_PREFIX
PYDICI_PAGES = ("/",
                "/search",
                "/search?q=lala",
                "/leads/1/",
                "/leads/2/",
                "/leads/3/",
                "/admin/",
                "/leads/csv/all",
                "/leads/csv/active",
                "/leads/graph/bar-jqp",
                "/leads/sendmail/2/",
                "/leads/mail/text",
                "/leads/mail/html",
                "/leads/review",
                "/feeds/latest/",
                "/feeds/mine/",
                "/feeds/new/",
                "/feeds/won/",
                "/feeds/latestStaffing/",
                "/feeds/myLatestStaffing/",
                "/feeds/archivedMission/",
                "/staffing/pdcreview/",
                "/staffing/pdcreview/2009/07",
                "/staffing/mission/",
                "/staffing/mission/all",
                "/staffing/mission/1/",
                "/staffing/mission/1/#tab-staffing",
                "/staffing/mission/1/#tab-timesheet",
                "/staffing/mission/2/",
                "/staffing/mission/2/#tab-staffing",
                "/staffing/mission/2/#tab-timesheet",
                "/staffing/mission/3/",
                "/staffing/mission/3/#tab-staffing",
                "/staffing/mission/3/#tab-timesheet",
                "/staffing/forecast/consultant/1/",
                "/staffing/timesheet/consultant/1/",
                "/staffing/timesheet/consultant/1/?csv",
                "/staffing/timesheet/consultant/1/2010/10",
                "/staffing/timesheet/consultant/1/2010/10/2",
                "/staffing/timesheet/all",
                "/staffing/timesheet/all/?csv",
                "/staffing/timesheet/all/2010/11",
                "/staffing/timesheet/detailed/?",
                "/staffing/timesheet/detailed/2010/11",
                "/staffing/graph/profile-rates/",
                "/staffing/graph/timesheet-rates/",
                "/staffing/graph/rates/consultant/1",
                "/staffing/mission/1/deactivate",
                "/people/home/consultant/1/",
                "/people/home/consultant/2/",
                "/people/home/consultant/3/",
                "/people/home/consultant/1/#tab-staffing",
                "/people/home/consultant/1/#tab-timesheet",
                "/crm/company/1/",
                "/crm/company/",
                "/crm/company/graph/sales",
                "/crm/company/graph/sales/lastyear",
                "/billing/graph/bar",
                "/billing/bill_review",
                "/billing/bill_delay",
                "/forbiden",
                "/admin/",
                "/admin/crm/",
                "/admin/crm/client/",
                "/admin/crm/subsidiary/",
                "/admin/crm/company/",
                "/admin/crm/contact/",
                "/admin/crm/businessbroker/",
                "/admin/crm/supplier/",
                "/admin/crm/administrativefunction/",
                "/admin/crm/administrativecontact/",
                "/admin/crm/missioncontact/",
                "/admin/crm/clientorganisation/",
                "/admin/leads/",
                "/admin/leads/lead/",
                )

PYDICI_MOBILE_PAGES = ("/mobile",
                      )


class SimpleTest(TestCase):
    fixtures = ["auth.json", "people.json", "crm.json",
                "leads.json", "staffing.json", "billing.json"]

    def test_basic_page(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        for page in PYDICI_PAGES:
            response = self.client.get(PREFIX + page)
            self.failUnlessEqual(response.status_code, 200,
                                 "Failed to test url %s (got %s instead of 200" % (page, response.status_code))

    def test_basic_mobile_page(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        for page in PYDICI_MOBILE_PAGES + PYDICI_PAGES[1:]:  # Remove first URL from PYDICI_PAGES (/) that disable mobile mode
            response = self.client.get(PREFIX + page)
            self.failUnlessEqual(response.status_code, 200,
                                 "Failed to test url %s (got %s instead of 200" % (page, response.status_code))

    def test_page_with_args(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        searchParams = {"lead": "on", "mission": "on", "company": "on", "contact": "on",
                        "consultant": "on", "bill": "on"}
        for page, args in  (("/search", {"q": "a"}),
                            ("/search", {"q": "sre"}),
                            ("/search", {"q": "a+e"})
                            ):
            args.update(searchParams)
            response = self.client.get(PREFIX + page, args)
            self.failUnlessEqual(response.status_code, 200,
                                 "Failed to test url %s (got %s instead of 200" % (page, response.status_code))

    def test_redirect(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        response = self.client.get(PREFIX + "/help")
        self.failUnlessEqual(response.status_code, 301)
        for page in ("/staffing/mission/newfromdeal/1/",
                     "/staffing/mission/newfromdeal/2/",
                     "/staffing/forecast/mission/1/",
                     "/staffing/forecast/mission/2/",
                     "/staffing/forecast/mission/3/",
                     "/staffing/timesheet/mission/1/",
                     "/staffing/timesheet/mission/2/",
                     "/staffing/timesheet/mission/3/",
                     "/people/detail/consultant/1/",
                     ):
            response = self.client.get(PREFIX + page)
            self.failUnlessEqual(response.status_code, 302)

    def test_not_found_page(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        for page in (PREFIX + "/leads/234/",
                     PREFIX + "/leads/sendmail/434/"):
            response = self.client.get(page)
            self.failUnlessEqual(response.status_code, 404,
                                 "Failed to test url %s (got %s instead of 404" % (page, response.status_code))

    def test_pdc_review(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        url = PREFIX + "/staffing/pdcreview/2009/07"
        for arg in ({}, {"projected": None}, {"groupby": "manager"}, {"groupby": "position"},
                    {"n_month": "5"}, {"n_month": "50"}):
            response = self.client.get(url, arg)
            self.failUnlessEqual(response.status_code, 200,
                "Failed to test pdc_review with arg %s (got %s instead of 200" % (arg, response.status_code))


class UtilsTest(TestCase):
    def test_monthWeekNumber(self):
        # Week number, date
        dates = ((1, date(2011, 4, 1)),
                 (1, date(2011, 4, 3)),
                 (2, date(2011, 4, 4)),
                 (2, date(2011, 4, 10)),
                 (5, date(2011, 4, 30)))
        for weekNum, weekDate in dates:
            self.assertEqual(weekNum, monthWeekNumber(weekDate))

    def test_previousWeek(self):
        # Previous week first day, week day
        dates = ((date(2011, 3, 28), date(2011, 4, 1)),
                 (date(2011, 3, 28), date(2011, 4, 2)),
                 (date(2011, 3, 28), date(2011, 4, 3)),
                 (date(2011, 4, 1), date(2011, 4, 4)),
                 (date(2011, 4, 1), date(2011, 4, 10)),
                 (date(2011, 4, 18), date(2011, 4, 30)),
                 (date(2010, 12, 27), date(2011, 1, 1)),
                 (date(2010, 12, 27), date(2011, 1, 2)),
                 (date(2011, 1, 1), date(2011, 1, 3)),
                 )
        for firstDay, weekDay in dates:
            self.assertEqual(firstDay, previousWeek(weekDay))

    def test_nextWeek(self):
        # Previous week first day, week day
        dates = ((date(2011, 4, 4), date(2011, 4, 1)),
                 (date(2011, 4, 4), date(2011, 4, 2)),
                 (date(2011, 4, 4), date(2011, 4, 3)),
                 (date(2011, 4, 11), date(2011, 4, 4)),
                 (date(2011, 4, 11), date(2011, 4, 10)),
                 (date(2011, 5, 1), date(2011, 4, 30)),
                 (date(2011, 5, 2), date(2011, 5, 1)),
                 (date(2011, 1, 1), date(2010, 12, 31)),
                 (date(2011, 1, 3), date(2011, 1, 1)),
                 (date(2011, 1, 3), date(2011, 1, 2)),
                 (date(2011, 1, 10), date(2011, 1, 3)),
                 )
        for firstDay, weekDay in dates:
            self.assertEqual(firstDay, nextWeek(weekDay))


class CrmModelTest(TestCase):
    fixtures = ["auth.json", "people.json", "crm.json",
                "leads.json", "staffing.json", "billing.json"]

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


class LeadModelTest(TestCase):
    fixtures = ["auth.json", "people.json", "crm.json",
                "leads.json", "staffing.json", "billing.json"]

    def setUp(self):
        if not os.path.exists(pydici.settings.DOCUMENT_PROJECT_PATH):
            os.makedirs(pydici.settings.DOCUMENT_PROJECT_PATH)

    def test_create_lead(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        lead = create_lead()
        self.failUnlessEqual(lead.staffing.count(), 0)
        self.failUnlessEqual(lead.staffing_list(), ", (JCF)")
        lead.staffing.add(Consultant.objects.get(pk=1))
        self.failUnlessEqual(lead.staffing.count(), 1)
        self.failUnlessEqual(len(lead.update_date_strf()), 14)
        self.failUnlessEqual(lead.staffing_list(), "SRE, (JCF)")
        self.failUnlessEqual(lead.short_description(), "A wonderfull lead th...")
        self.failUnlessEqual(urlresolvers.reverse("leads.views.detail", args=[4]), PREFIX + "/leads/4/")

        url = "".join(urlparse.urlsplit(urlresolvers.reverse("leads.views.detail", args=[4]))[2:])
        response = self.client.get(url)
        self.failUnlessEqual(response.status_code, 200)
        context = response.context[-1]
        self.failUnlessEqual(unicode(context["lead"]), u"World company : DSI  - laala")
        self.failUnlessEqual(unicode(context["user"]), "sre")

    def test_save_lead(self):
        subsidiary = Subsidiary.objects.get(pk=1)
        broker = BusinessBroker.objects.get(pk=1)
        client = Client.objects.get(pk=1)
        lead = Lead(name="laalaa",
          state="QUALIF",
          client=client,
          salesman=None,
          description="A wonderfull lead that as a so so long description",
          subsidiary=subsidiary)
        deal_id = client.organisation.company.code, date.today().strftime("%y")
        self.assertEqual(lead.deal_id, "")  # No deal id code yet
        lead.save()
        self.assertEqual(lead.deal_id, "%s%s01" % deal_id)
        lead.paying_authority = broker
        lead.save()
        self.assertEqual(lead.deal_id, "%s%s01" % deal_id)
        lead.deal_id = ""
        lead.save()
        self.assertEqual(lead.deal_id, "%s%s02" % deal_id)  # 01 is already used

    def test_save_lead_and_active_client(self):
        lead = Lead.objects.get(id=1)
        lead.state = "LOST"
        lead.save()
        lead = Lead.objects.get(id=1)
        self.assertTrue(lead.client.active)  # There's still anotger active lead for this client
        otherLead = Lead.objects.get(id=3)
        otherLead.state = "SLEEPING"
        otherLead.save()
        lead = Lead.objects.get(id=1)
        self.assertFalse(lead.client.active)
        newLead = Lead()
        newLead.subsidiary_id = 1
        newLead.client = lead.client
        newLead.save()
        self.assertTrue(lead.client.active)  # A new lead on this client should mark it as active again

    def test_lead_done_work(self):
        for i in (1, 2, 3):
            lead = Lead.objects.get(id=i)
            a, b = lead.done_work()
            c, d = lead.done_work_k()
            e = lead.unused()
            f = lead.totalObjectiveMargin()
            for x in (a, b, c, d, e, f):
                self.assertIsInstance(x, (int, float, Decimal))

    def test_checkDoc(self):
        for i in (1, 2, 3):
            lead = Lead.objects.get(id=i)
            lead.checkDeliveryDoc()
            lead.checkBusinessDoc()


class StaffingModelTest(TestCase):
    fixtures = ["auth.json", "people.json", "crm.json",
                "leads.json", "staffing.json", "billing.json"]

    def test_save_mission_and_active_client(self):
        mission = Mission.objects.get(id=1)
        mission.save()
        lead = mission.lead
        for lead in Lead.objects.filter(id__in=(1, 2, 3)):
            # Set lead as won to allow client passivation when mission are archived
            lead.state = "WON"
            lead.save()
        mission.active = False
        self.assertTrue(mission.lead.client.active)  # Client is active by default and mission is not saved
        mission.save()
        self.assertFalse(mission.lead.client.active)  # Client should be flag as inactive too
        # Now with a client that has two mission in two different leads
        mission = Mission.objects.get(id=2)
        mission.save()
        self.assertTrue(mission.lead.client.active)
        mission.active = False
        mission.save()
        self.assertTrue(mission.lead.client.active)  # Client is still active because another mission is active
        otherMission = Mission.objects.get(id=3)
        otherMission.active = False
        otherMission.save()
        mission = Mission.objects.get(id=2)  # Read mission from database to avoid nasty cache effect
        self.assertFalse(mission.lead.client.active)  # All missions are now archived. Client is no more active

    def test_save_mission_and_forecast(self):
        mission = Mission.objects.get(id=1)
        mission.save()
        self.assertNotEqual(mission.staffing_set.count(), 0)
        mission.active = False
        mission.save()
        self.assertEqual(mission.staffing_set.count(), 0)


class WorkflowTest(TestCase):
    """Test pydici workflows"""
    fixtures = ["auth.json", "people.json", "crm.json",
                "leads.json", "staffing.json", "billing.json"]

    def test_expense_wf(self):
        # Setup default workflow
        install_expense_workflow()

        ABR = Consultant.objects.get(trigramme="ABR")
        TCO = Consultant.objects.get(trigramme="TCO")
        tco = TCO.getUser()
        abr = ABR.getUser()
        fla = User.objects.get(username="fla")
        category = ExpenseCategory.objects.create(name="repas")
        e = Expense.objects.create(user=tco, description="une grande bouffe",
                                   category=category, amount=123,
                                   creation_date=date.today(), expense_date=date.today())
        self.assertEqual(wf.get_state(e), None)
        wf.set_initial_state(e)
        self.assertNotEqual(wf.get_state(e), None)  # Now wf is setup

        # state = requested
        self.assertEqual(len(wf.get_allowed_transitions(e, tco)), 0)  # No transition allowed for user
        self.assertEqual(len(wf.get_allowed_transitions(e, fla)), 0)  # No transition allowed for paymaster
        self.assertEqual(len(wf.get_allowed_transitions(e, abr)), 2)  # But for his manager accept/reject

        # Reject it
        reject = Transition.objects.get(name="reject")
        self.assertTrue(wf.do_transition(e, reject, abr))
        for user in (tco, abr, fla):
            self.assertEqual(len(wf.get_allowed_transitions(e, user)), 0)  # No transition allowed

        # Validate it
        wf.set_initial_state(e)  # Returns to requested state
        validate = Transition.objects.get(name="validate")
        self.assertTrue(wf.do_transition(e, validate, abr))
        for user in (tco, abr):
            self.assertEqual(len(wf.get_allowed_transitions(e, user)), 0)  # No transition allowed
        self.assertEqual(len(wf.get_allowed_transitions(e, fla)), 2)  # Except paymaster accept/ask info

        # Ask information
        ask = Transition.objects.get(name="ask information")
        self.assertTrue(wf.do_transition(e, ask, fla))
        self.assertTrue(perm.has_permission(e, tco, "expense_edit"))
        wf.set_initial_state(e)  # Returns to requested state
        self.assertEqual(len(wf.get_allowed_transitions(e, tco)), 0)  # No transition allowed for user
        self.assertTrue(wf.do_transition(e, validate, abr))  # Validate it again

        # Check it
        control = Transition.objects.get(name="control")
        self.assertTrue(wf.do_transition(e, control, fla))
        for user in (tco, abr, fla):
            self.assertEqual(len(wf.get_allowed_transitions(e, user)), 0)  # No transition allowed

        # Create a payment for that expense
        expensePayment = ExpensePayment(payment_date=date.today())
        expensePayment.save()
        e.expensePayment = expensePayment
        e.save()
        self.assertEqual(expensePayment.user(), tco)
        self.assertEqual(expensePayment.amount(), 123)


# ######
def create_lead():
    """Create test lead
    @return: lead object"""
    lead = Lead(name="laala",
          due_date="2008-11-01",
          update_date="2008-11-01 16:14:16",
          creation_date="2008-11-01 15:43:43",
          start_date="2008-11-01",
          responsible=None,
          sales=None,
          external_staffing="JCF",
          state="QUALIF",
          deal_id="123456",
          client=Client.objects.get(pk=1),
          salesman=None,
          description="A wonderfull lead that as a so so long description",
          subsidiary=Subsidiary.objects.get(pk=1))

    lead.save()
    return lead
