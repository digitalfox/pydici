# coding: utf-8
"""
Test cases
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

# Python/Django test modules
from django.test import TestCase, TransactionTestCase
from django.core import urlresolvers
from django.contrib.auth.models import Group, User
from django.db import IntegrityError
from django.test import RequestFactory
from django.contrib.messages.storage import default_storage
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.conf import settings


# Third party modules
import workflows.utils as wf
import permissions.utils as perm
from workflows.models import Transition

# Pydici modules
from core.utils import monthWeekNumber, previousWeek, nextWeek, nextMonth, previousMonth, cumulateList, capitalize
from core.models import GroupFeature, FEATURES
from leads.utils import postSaveLead
from leads.models import Lead
from leads import learn as leads_learn
from people.models import Consultant, ConsultantProfile, RateObjective
from crm.models import Client, Subsidiary, BusinessBroker, Supplier
from staffing.models import Mission, Staffing, Timesheet, FinancialCondition
from billing.models import SupplierBill, ClientBill
from expense.models import Expense, ExpenseCategory, ExpensePayment
from expense.default_workflows import install_expense_workflow
import pydici.settings

# Python modules used by tests
from urllib2 import urlparse
from datetime import date, datetime
import os
import os.path
import sys
from decimal import Decimal
from subprocess import Popen, PIPE
import json


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
                "/staffing/production-report/",
                "/staffing/production-report/2009/07",
                "/staffing/fixed-price-mission-report/",
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
                "/staffing/timesheet/all",
                "/staffing/timesheet/all/?csv",
                "/staffing/timesheet/all/2010/11",
                "/staffing/timesheet/detailed/?",
                "/staffing/timesheet/detailed/2010/11",
                "/staffing/graph/profile-rates/",
                "/staffing/graph/timesheet-rates/",
                "/staffing/mission/1/deactivate",
                "/people/home/consultant/1/",
                "/people/home/consultant/2/",
                "/people/home/consultant/3/",
                "/people/home/consultant/1/#tab-staffing",
                "/people/home/consultant/1/#tab-timesheet",
                "/crm/company/1/detail",
                "/crm/company/all",
                "/billing/graph/billing-jqp",
                "/billing/bill_review",
                "/billing/bill_delay",
                "/risks",
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

PYDICI_AJAX_PAGES = (
                "/staffing/forecast/consultant/1/",
                "/staffing/timesheet/consultant/1/",
                "/staffing/timesheet/consultant/1/?csv",
                "/staffing/timesheet/consultant/1/2010/10",
                "/staffing/timesheet/consultant/1/2010/10/2",
                "/leads/graph/bar-jqp",
                "/crm/company/graph/sales",
                "/crm/company/graph/sales/lastyear",
)

PYDICI_FIXTURES = ["auth.json", "people.json", "crm.json",
                "leads.json", "staffing.json", "billing.json"]

class SimpleTest(TestCase):
    fixtures = PYDICI_FIXTURES

    def setUp(self):
        setup_test_user_features()

    def test_basic_page(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        for page in PYDICI_PAGES + PYDICI_AJAX_PAGES:
            response = self.client.get(PREFIX + page)
            self.failUnlessEqual(response.status_code, 200,
                                 "Failed to test url %s (got %s instead of 200" % (page, response.status_code))


    def test_page_with_args(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        for page, args in  (("/search", {"q": "a"}),
                            ("/search", {"q": "sre"}),
                            ("/search", {"q": "a+e"})
                            ):
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

    def test_cumulateList(self):
        self.assertListEqual(cumulateList([1, 2, 3]), [1, 3, 6])
        self.assertListEqual(cumulateList([]), [])
        self.assertListEqual(cumulateList([8]), [8])

    def test_capitalize(self):
        data = ((u"coucou", u"Coucou"),
                (u"état de l'art", u"État De L'Art"),
                (u"fusion du si", u"Fusion Du Si"),
                (u"cohérence du SI", u"Cohérence Du SI"),
                (u"test-and-learn", u"Test-And-Learn"))
        for word, capitalizeddWord in data:
            self.assertEqual(capitalizeddWord, capitalize(word))

class StaffingViewsTest(TestCase):
    fixtures = PYDICI_FIXTURES

    def setUp(self):
        setup_test_user_features()


    def test_mission_timesheet(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        current_month = date.today().replace(day=1)
        next_month = nextMonth(current_month)
        previous_month = previousMonth(current_month)
        lead = Lead.objects.get(id=1)
        c1 = Consultant.objects.get(id=1)
        c2 = Consultant.objects.get(id=2)
        mission = Mission(lead=lead, subsidiary_id=1, billing_mode="TIME_SPENT", nature="PROD", probability=100)
        mission.save()
        response = self.client.get(urlresolvers.reverse("staffing.views.mission_timesheet", args=[mission.id,]), follow=True, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["margin"], 0)
        self.assertEqual(response.context["objective_margin_total"], 0)
        self.assertEqual(response.context["forecasted_unused"], 0)
        self.assertEqual(response.context["current_unused"], 0)
        self.assertEqual(response.context["avg_daily_rate"], 0)
        # Add some forecast
        Staffing(mission=mission, staffing_date=current_month, consultant=c1, charge=15).save()
        Staffing(mission=mission, staffing_date=current_month, consultant=c2, charge=10).save()
        Staffing(mission=mission, staffing_date=next_month, consultant=c1, charge=8).save()
        Staffing(mission=mission, staffing_date=next_month, consultant=c2, charge=6).save()
        # Add some timesheet - we fake with all charge on the first day
        Timesheet(mission=mission, working_date=previous_month, consultant=c1, charge=8).save()
        Timesheet(mission=mission, working_date=previous_month, consultant=c2, charge=5).save()
        Timesheet(mission=mission, working_date=current_month, consultant=c1, charge=11).save()
        Timesheet(mission=mission, working_date=current_month, consultant=c2, charge=9).save()
        # Define objective rates for consultants
        RateObjective(consultant=c1, start_date=previous_month, rate=700, rate_type="DAILY_RATE").save()
        RateObjective(consultant=c2, start_date=previous_month, rate=1050, rate_type="DAILY_RATE").save()
        # Add financial conditions for this mission
        FinancialCondition(consultant=c1, mission=mission, daily_rate=800).save()
        FinancialCondition(consultant=c2, mission=mission, daily_rate=1100).save()
        # Define mission price
        mission.price = 50
        mission.save()
        # Let's test if computation are rights
        response = self.client.get(urlresolvers.reverse("staffing.views.mission_timesheet", args=[mission.id,]), follow=True, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["margin"], 0)  # That's because we are in fixed price
        self.assertEqual(response.context["objective_margin_total"], 2600)
        self.assertEqual(response.context["forecasted_unused"], 2.1)
        self.assertEqual(response.context["current_unused"], 19.4)
        # Switch to fixed price mission
        mission.billing_mode = "FIXED_PRICE"
        mission.save()
        response = self.client.get(urlresolvers.reverse("staffing.views.mission_timesheet", args=[mission.id,]), follow=True, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["margin"], 2.1)
        self.assertEqual(response.context["objective_margin_total"], 2600)
        self.assertEqual(response.context["forecasted_unused"], 0)  # Unused is margin in fixes price :-)
        self.assertEqual(response.context["current_unused"], 0)  # idem
        # Check mission data main table
        data = response.context["mission_data"]
        self.assertListEqual(data[0], [c2, [5, 9, 14, 15.4], [1, 6, 7, 7.7], [21, 23.1]])
        self.assertListEqual(data[1], [c1, [8, 11, 19, 15.2], [4, 8, 12, 9.6], [31, 24.8]])
        self.assertListEqual(data[2], [None, [13, 20, 33, 30.6], [5, 14, 19, 17.3], [52, 47.9],
                                       [11.9, 18.7], [4.3, 13],
                                       [915.4, 935, 927.3], [860, 928.6, 910.5]])



class CrmModelTest(TestCase):
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


class CrmViewsTest(TestCase):
    fixtures = PYDICI_FIXTURES

    def setUp(self):
        setup_test_user_features()

    def test_client_all_in_one(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        view = urlresolvers.reverse("crm.views.client_organisation_company_popup")
        error_tag = "form-group has-error"

        # Initial data
        data = { "client-expectations": "3_FLAT",
                 "client-alignment": "2_STANDARD",
                 "client-contact": "",
                 "contact-name": "",
                 "contact-email": "",
                 "contact-function": "",
                 "contact-mobile_phone": "",
                 "contact-phone": "",
                 "contact-fax": "",
                 "organisation-name": "",
                 "company-name": "",
                 "company-code": "",
                 "company-web": "" }

        # Remove existing client that we will create
        Client.objects.get(id=1).delete()

        # Incomplete form with initial data
        response = self.client.post(view, data=data, follow=True)
        self.check_client_popup_response_is_ko(response)

        # Simple form with existing organisation
        data["client-organisation"] = 1
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response)
        client.delete()

        # Same with existing contact
        data["client-contact"] = 1
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response)
        self.assertEqual(client.contact.id, 1)
        client.delete()

        # Same with a new contact, but incomplete
        del data["client-contact"]
        data["contact-mail"] = "Joe@worldcompany.com"
        response = self.client.post(view, data=data, follow=True)
        # Yes it works. We cannot distinguish incomplete contact and no contact, so, incomplete contact is ignored
        client = self.check_client_popup_response_is_ok(response)
        client.delete()

        # And now with a complete new contact
        data["contact-name"] = "Joe"
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response)
        self.assertEquals(client.contact.name, "Joe")
        client.delete()

        # Time to create organisation with existing company
        del data["client-organisation"]
        data["organisation-name"] = "blabla"
        data["organisation-company"] = 1
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response)
        self.assertEquals(client.organisation.name, "blabla")
        self.assertEquals(client.organisation.company.id, 1)
        client.delete()

        # Incomplete new organisation should fail
        del data["organisation-name"]
        response = self.client.post(view, data=data, follow=True)
        self.check_client_popup_response_is_ko(response)

        # Incomplete new company should fail
        del data["organisation-company"]
        data["organisation-name"] = "youpala"
        data["company-name"] = "The youpala company"
        response = self.client.post(view, data=data, follow=True)
        self.check_client_popup_response_is_ko(response)

        # All-in. Create new organisation and a new company
        data["company-code"] = "YOU"
        data["company-businessOwner"] = 1
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response)
        self.assertEquals(client.organisation.name, "youpala")
        self.assertEquals(client.organisation.company.code, "YOU")


    def check_client_popup_response_is_ok(self, response):
        """Ensure POST form is ok and return created client"""
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data["success"])
        # self.assertNotIn(error_tag, response_data["form"])
        self.assertIn("client_id", response_data)
        self.assertIn("client_name", response_data)
        return Client.objects.get(id=int(response_data["client_id"]))

    def check_client_popup_response_is_ko(self, response):
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertFalse(response_data["success"])
        # self.assertIn(error_tag, response_data["form"])




class LeadModelTest(TestCase):
    fixtures = PYDICI_FIXTURES

    def setUp(self):
        setup_test_user_features()
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
        lead = Lead.objects.get(id=1)
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
    fixtures = PYDICI_FIXTURES

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


class BillingModelTest(TransactionTestCase):
    """Test Billing application model"""
    fixtures = PYDICI_FIXTURES

    def test_save_supplier_bill(self):
        lead = Lead.objects.get(id=1)
        supplier = Supplier.objects.get(id=1)
        bill = SupplierBill()
        self.assertEqual(bill.state, "1_RECEIVED")
        self.assertRaises(IntegrityError, bill.save)  # No lead, no supplier and no amount
        bill.lead = lead
        bill.supplier = supplier
        self.assertRaises(IntegrityError, bill.save)  # Still no amount
        bill.amount = 100
        self.assertIsNone(bill.amount_with_vat)
        bill.save()
        self.assertIsNone(bill.amount_with_vat)  # No auto computation of VAT for supplier bill
        self.assertEqual(bill.payment_delay(), 0)
        self.assertEqual(bill.payment_wait(), -30)
        bill.payment_date = date.today()
        bill.save()
        self.assertEqual(bill.state, "2_PAID")


    def test_save_client_bill(self):
        lead = Lead.objects.get(id=1)
        client = Client.objects.get(id=1)
        bill = ClientBill()
        self.assertEqual(bill.state, "1_SENT")
        self.assertRaises(IntegrityError, bill.save)  # No lead, no client and no amount
        bill.lead = lead
        bill.client = client
        self.assertRaises(IntegrityError, bill.save)  # Still no amount
        bill.amount = 100
        self.assertIsNone(bill.amount_with_vat)
        bill.save()
        self.assertIsNotNone(bill.amount_with_vat)
        self.assertEqual(bill.state, "1_SENT")
        self.assertEqual(bill.payment_delay(), 0)
        self.assertEqual(bill.payment_wait(), -30)
        bill.payment_date = date.today()
        bill.save()
        self.assertEqual(bill.state, "2_PAID")



class WorkflowTest(TestCase):
    """Test pydici workflows"""
    fixtures = PYDICI_FIXTURES

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
                                   category=category, amount=123, chargeable=False,
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


class LeadLearnTestCase(TestCase):
    """Test lead state proba learn"""
    fixtures = PYDICI_FIXTURES

    def test_model(self):
        if not leads_learn.HAVE_SCIKIT:
            return
        r1 = Consultant.objects.get(id=1)
        r2 = Consultant.objects.get(id=2)
        c1 = Client.objects.get(id=1)
        c2 = Client.objects.get(id=1)
        for i in range(20):
            a = create_lead()
            if a.id%2:
                a.state = "WON"
                a.sales = a.id
                a.client= c1
                a.responsible = r1
            else:
                a.state = "FORGIVEN"
                a.sales = a.id
                a.client = c2
                a.responsible = r2
            a.save()
        leads_learn.eval_state_model()
        self.assertGreater(leads_learn.test_state_model(), 0.8, "Proba is too low")


    def test_too_few_lead(self):
        lead = create_lead()
        f = RequestFactory()
        request = f.get("/")
        request.user = User.objects.get(id=1)
        request.session = {}
        request._messages = default_storage(request)
        lead = create_lead()
        postSaveLead(request, lead, [], sync=True)  # Learn model cannot exist, but it should not raise error


    def test_mission_proba(self):
        for i in range(5):
            # Create enough data to allow learn model to exist
            a = create_lead()
            a.state="WON"
            a.save()
        lead = Lead.objects.get(id=1)
        lead.state="LOST"  # Need more than one target class to build a solver
        lead.save()
        f = RequestFactory()
        request = f.get("/")
        request.user = User.objects.get(id=1)
        request.session = {}
        request._messages = default_storage(request)
        lead = create_lead()
        lead.state = "OFFER_SENT"
        lead.save()
        postSaveLead(request, lead, [], sync=True)
        mission = lead.mission_set.all()[0]
        if leads_learn.HAVE_SCIKIT:
            self.assertEqual(mission.probability, lead.stateproba_set.get(state="WON").score)
        else:
            self.assertEqual(mission.probability, 50)
        lead.state = "WON"
        lead.save()
        postSaveLead(request, lead, [], sync=True)
        mission = Mission.objects.get(id=mission.id)  # reload it
        self.assertEqual(mission.probability, 100)


class JsTest(StaticLiveServerTestCase):
    """Test page through fake browser (phantomjs) to check that javascript stuff is going well"""
    fixtures = PYDICI_FIXTURES
    def test_missing_resource_and_js_errors(self):
        # Add a check to skip if casperjs is not available
        setup_test_user_features()
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        urls = ",".join([self.live_server_url + PREFIX + page for page in PYDICI_PAGES])
        test_filename = os.path.join(os.path.dirname(__file__), 'tests.js')
        self.assertTrue(run_casper(test_filename, self.client, verbose=False, urls = urls), "At least one Casper test failed. See above the detailed log.")


# ###### Test utils
def create_lead():
    """Create test lead
    @return: lead object"""
    lead = Lead(name="laala",
          due_date=date(2008,11,01),
          update_date=datetime(2008, 11, 1, 15,55,40),
          creation_date=datetime(2008, 11, 1, 15,43,43),
          start_date=date(2008, 11, 01),
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


def setup_test_user_features():
    admin_group = Group(name="admin")
    admin_group.save()
    for name in FEATURES:
        GroupFeature(feature=name, group=admin_group).save()

    test_user = User.objects.get(username=TEST_USERNAME)
    test_user.groups.add(admin_group)
    test_user.save()


def run_casper(test_filename, client, **kwargs):
    """Casperjs launcher"""
    env = os.environ.copy()
    env["PATH"] += ":" + os.path.join(os.path.expanduser("~"), "node_modules/.bin/")
    verbose = kwargs.pop("verbose", False)
    cookie_name = settings.SESSION_COOKIE_NAME
    if cookie_name in client.cookies:
        kwargs["cookie-name"] = cookie_name
        kwargs["cookie-value"] = client.cookies[cookie_name].value
    if verbose:
        kwargs["log-level"] = "debug"
    else:
        kwargs["log-level"] = "error"
    cmd = ["casperjs", "--web-security=no", "test"]
    cmd.extend([("--%s=%s" % i) for i in kwargs.iteritems()])
    cmd.append(test_filename)
    try:
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, env=env, cwd=os.path.dirname(test_filename))
        out, err = p.communicate()
    except OSError:
        print "WARNING: casperjs is not installed or properly setup. Skipping JS Tests..."
        return True
    if verbose or p.returncode:
        sys.stdout.write(out)
        sys.stderr.write(err)
    return p.returncode == 0
