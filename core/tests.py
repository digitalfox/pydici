# coding: utf-8
"""
Test cases
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

# Python/Django test modules
from django.test import TestCase
from django.core import urlresolvers
from django.contrib.admin.models import User

# Third party modules
import workflows.utils as wf
import permissions.utils as perm
from workflows.models import Transition

# Pydici modules
from pydici.core.models import Subsidiary
from pydici.leads.models import Lead
from pydici.people.models import Consultant, ConsultantProfile
from pydici.crm.models import Client
from pydici.staffing.models import Mission
from pydici.expense.models import Expense, ExpenseCategory
from pydici.expense.default_workflows import install_expense_workflow
import pydici.settings

# Python modules used by tests
from urllib2 import urlparse
from datetime import date

TEST_USERNAME = "sre"
TEST_PASSWORD = "sre"
PREFIX = "/" + pydici.settings.PYDICI_PREFIX

class SimpleTest(TestCase):
    fixtures = ["auth.json", "core.json", "people.json", "crm.json",
                "leads.json", "staffing.json", "billing.json"]


    def test_basic_page(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        for page in ("/",
                     "/search",
                     "/search?q=lala",
                     "/leads/1/",
                     "/leads/2/",
                     "/leads/3/",
                     "/admin/",
                     "/leads/csv/all",
                     "/leads/csv/active",
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
                     "/staffing/pdcreview/",
                     "/staffing/pdcreview/2009/07",
                     "/staffing/mission/",
                     "/staffing/mission/all",
                     "/staffing/forecast/mission/1/",
                     "/staffing/forecast/mission/2/",
                     "/staffing/forecast/mission/3/",
                     "/staffing/forecast/consultant/1/",
                     "/staffing/timesheet/mission/1/",
                     "/staffing/timesheet/mission/2/",
                     "/staffing/timesheet/mission/3/",
                     "/staffing/timesheet/consultant/1/",
                     "/staffing/timesheet/consultant/1/?csv",
                     "/staffing/timesheet/consultant/1/2010/10",
                     "/staffing/timesheet/consultant/1/2010/10/2",
                     "/staffing/timesheet/all",
                     "/staffing/timesheet/all/?csv",
                     "/staffing/timesheet/all/2010/11",
                     "/staffing/graph/rates/",
                     "/staffing/graph/rates/pie/consultant/1",
                     "/staffing/graph/rates/graph/consultant/1",
                     "/staffing/mission/1/deactivate",
                     "/leads/graph/pie",
                     "/leads/graph/bar",
                     "/people/consultant/1/",
                     "/people/consultant/2/",
                     "/people/consultant/3/",
                     "/crm/company/1/",
                     "/crm/company/",
                     "/billing/graph/bar",
                     "/billing/bill_review",
                     "/billing/bill_delay",
                     "/forbiden",
                     ):
            response = self.client.get(PREFIX + page)
            self.failUnlessEqual(response.status_code, 200,
                                 "Failed to test url %s (got %s instead of 200" % (page, response.status_code))

    def test_page_with_args(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        searchParams = {"lead":"on", "mission":"on", "company":"on", "contact":"on",
                        "consultant":"on", "bill":"on"}
        for page, args in  (("/search", {"q":"a"}),
                            ("/search", {"q":"sre"}),
                            ("/search", {"q":"a+e"})
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
                     "/staffing/rate/mission/1/consultant/1/"):
            response = self.client.get(PREFIX + page)
            self.failUnlessEqual(response.status_code, 302)

    def test_not_found_page(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        for page in (PREFIX + "/leads/234/",
                     PREFIX + "/leads/sendmail/434/"):
            response = self.client.get(page)
            self.failUnlessEqual(response.status_code, 404,
                                 "Failed to test url %s (got %s instead of 404" % (page, response.status_code))

    def test_create_lead(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        lead = create_lead()
        self.failUnlessEqual(lead.staffing.count(), 0)
        lead.staffing.add(Consultant.objects.get(pk=1))
        self.failUnlessEqual(lead.staffing.count(), 1)
        # Add staffing here lead.add...
        self.failUnlessEqual(len(lead.update_date_strf()), 14)
        self.failUnlessEqual(lead.staffing_list(), "SRE, (JCF)")
        self.failUnlessEqual(lead.short_description(), "A wonderfull lead th...")
        self.failUnlessEqual(urlresolvers.reverse("pydici.leads.views.detail", args=[4]), PREFIX + "/leads/4/")

        url = "".join(urlparse.urlsplit(urlresolvers.reverse("pydici.leads.views.detail", args=[4]))[2:])
        response = self.client.get(url)
        self.failUnlessEqual(response.status_code, 200)
        context = response.context[-1]
        self.failUnlessEqual(unicode(context["lead"]), u"World company : DSI  - laala")
        self.failUnlessEqual(unicode(context["user"]), "sre")

    def test_pdc_review(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        url = PREFIX + "/staffing/pdcreview/2009/07"
        for arg in ({}, {"projected":None}, {"groupby": "manager"}, {"groupby": "position"},
                    {"n_month":"5"}, {"n_month":"50"}):
            response = self.client.get(url, arg)
            self.failUnlessEqual(response.status_code, 200,
                "Failed to test pdc_review with arg %s (got %s instead of 200" % (arg, response.status_code))

class UtilsTest(TestCase):
    def test_monthWeekNumber(self):
        from pydici.staffing.utils import monthWeekNumber
        # Week number, date
        dates = ((1, date(2011, 4, 1)),
                 (1, date(2011, 4, 3)),
                 (2, date(2011, 4, 4)),
                 (2, date(2011, 4, 10)),
                 (5, date(2011, 4, 30)))
        for weekNum, weekDate in dates:
            self.assertEqual(weekNum, monthWeekNumber(weekDate))

    def test_previousWeek(self):
        from pydici.staffing.utils import previousWeek
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
        from pydici.staffing.utils import nextWeek
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

class ModelTest(TestCase):
    fixtures = ["auth.json", "core.json", "people.json", "crm.json",
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

class WorkflowTest(TestCase):
    """Test pydici workflows"""
    fixtures = ["auth.json", "core.json", "people.json", "crm.json",
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
                                   category=category, amount=123, creation_date=date.today())
        self.assertEqual(wf.get_state(e), None)
        wf.set_initial_state(e)
        self.assertNotEqual(wf.get_state(e), None) # Now wf is setup

        # state = requested
        self.assertEqual(len(wf.get_allowed_transitions(e, tco)), 0) # No transition allowed for user
        self.assertEqual(len(wf.get_allowed_transitions(e, fla)), 0) # No transition allowed for paymaster
        self.assertEqual(len(wf.get_allowed_transitions(e, abr)), 2) # But for his manager accept/reject

        # Reject it
        reject = Transition.objects.get(name="reject")
        self.assertTrue(wf.do_transition(e, reject, abr))
        for user in (tco, abr, fla):
            self.assertEqual(len(wf.get_allowed_transitions(e, user)), 0) # No transition allowed

        # Validate it
        wf.set_initial_state(e) # Returns to requested state
        validate = Transition.objects.get(name="validate")
        self.assertTrue(wf.do_transition(e, validate, abr))
        for user in (tco, abr):
            self.assertEqual(len(wf.get_allowed_transitions(e, user)), 0) # No transition allowed
        self.assertEqual(len(wf.get_allowed_transitions(e, fla)), 2) # Except paymaster accept/ask info

        # Ask information
        ask = Transition.objects.get(name="ask information")
        self.assertTrue(wf.do_transition(e, ask, fla))
        self.assertTrue(perm.has_permission(e, tco, "expense_edit"))
        wf.set_initial_state(e) # Returns to requested state
        self.assertEqual(len(wf.get_allowed_transitions(e, tco)), 0) # No transition allowed for user
        self.assertTrue(wf.do_transition(e, validate, abr)) # Validate it again

        # Pay it
        pay = Transition.objects.get(name="pay")
        self.assertTrue(wf.do_transition(e, pay, fla))
        for user in (tco, abr, fla):
            self.assertEqual(len(wf.get_allowed_transitions(e, user)), 0) # No transition allowed


#######
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
          description="A wonderfull lead that as a so so long description")

    lead.save()
    return lead
