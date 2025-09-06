# coding: utf-8
"""
Test cases for billing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from datetime import date
import json

from django.test import TestCase, TransactionTestCase, RequestFactory
from django.db import IntegrityError
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils.translation import gettext as _

from crm.models import Supplier, Subsidiary
from billing.models import SupplierBill, ClientBill, BillDetail
from leads.models import Lead
from staffing.models import Timesheet, Mission, FinancialCondition
from people.models import Consultant
from core.tests import PYDICI_FIXTURES, setup_test_user_features, TEST_USERNAME
from core.utils import previousMonth, nextMonth
from billing.utils import get_client_billing_control_pivotable_data



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
        bill = ClientBill()
        self.assertEqual(bill.state, "0_DRAFT")
        self.assertRaises(Exception, bill.save)  # No lead, no client and no amount
        bill.lead = lead
        bill.amount = 100
        self.assertIsNone(bill.amount_with_vat)
        bill.save()
        # TODO: add billDetail test
        self.assertEqual(bill.state, "0_DRAFT")
        self.assertEqual(bill.payment_delay(), 0)
        self.assertEqual(bill.payment_wait(), -30)
        bill.payment_date = date.today()
        bill.state = "1_SENT"
        bill.save()
        self.assertEqual(bill.state, "2_PAID")

    def test_creation_lag_for_timespent(self):
        lead = Lead.objects.get(id=1)
        mission = lead.mission_set.first()
        mission.billing_mode = "TIME_SPENT"
        mission.save()
        ClientBill.objects.filter(lead=lead).delete()
        bill = ClientBill(lead=lead, creation_date=date(2010, 10, 5), state="1_SENT")
        bill.save()
        self.assertIsNone(bill.creation_lag())
        detail = BillDetail(bill=bill, mission=mission, quantity=10, unit_price=1000, month=date(2010, 9, 1))
        detail.save()
        self.assertEqual(bill.creation_lag(), 4)
        detail2 = BillDetail(bill=bill, mission=mission, quantity=10, unit_price=1000, month=date(2010, 8, 1))
        detail2.save()
        self.assertEqual(bill.creation_lag(), 34)
        detail.delete()
        self.assertEqual(bill.creation_lag(), 34)

    def test_creation_lag_for_fixedprice(self):
        lead = Lead.objects.get(id=1)
        mission = lead.mission_set.first()
        mission.billing_mode = "FIXED_PRICE"
        mission.save()
        consultant = Consultant.objects.get(id=1)
        ClientBill.objects.filter(lead=lead).delete()
        bill = ClientBill(lead=lead, creation_date=date(2010, 10, 5), state="1_SENT")
        bill.save()
        self.assertIsNone(bill.creation_lag())
        detail = BillDetail(bill=bill, mission=mission, quantity=0.3, unit_price=10000)
        detail.save()
        Timesheet.objects.filter(mission=mission).delete()
        self.assertIsNone(bill.creation_lag())  # no timesheet, no way to determine lag
        Timesheet(mission=mission, consultant=consultant, working_date=date(2010, 9, 10)).save()
        self.assertEqual(bill.creation_lag(), 25)
        Timesheet(mission=mission, consultant=consultant, working_date=date(2010, 10, 10)).save()
        self.assertEqual(bill.creation_lag(), 25)  # no change for first bill
        bill2 = ClientBill(lead=lead, creation_date=date(2010, 11, 10), state="1_SENT")
        bill2.save()
        detail2 = BillDetail(bill=bill2, mission=mission, quantity=0.7, unit_price=10000)
        detail2.save()
        self.assertEqual(bill.creation_lag(), 25)  # still no change for first bill
        self.assertEqual(bill2.creation_lag(), 31)

    def test_client_deal_id(self):
        lead = Lead.objects.get(id=1)
        mission = lead.mission_set.first()
        self.assertEqual(mission.client_deal_id, "")
        bill = ClientBill(lead=lead, creation_date=date(2010, 10, 5), state="1_SENT")
        bill.save()
        BillDetail(bill=bill, mission=mission, quantity=1, unit_price=1000).save()
        self.assertEqual(bill.client_deal_id, "")

        # With lead client deal id
        lead.client_deal_id = "123"
        lead.save()
        self.assertEqual(mission.client_deal_id, "")
        self.assertEqual(bill.client_deal_id, "")
        bill.save() # trigger inheritance
        self.assertEqual(bill.client_deal_id, "123")
        mission.save() # trigger inheritance
        self.assertEqual(mission.client_deal_id, "123")

        # With mission client deal id
        mission.client_deal_id = "123M"
        mission.save()
        self.assertEqual(bill.client_deal_id, "123") # still lead client deal id
        bill.save()
        self.assertEqual(bill.client_deal_id, "123")  # again, because id is defined
        bill.client_deal_id = ""
        bill.save() # trigger inheritance
        self.assertEqual(bill.client_deal_id, "123M")  # this time, inherit from mission

        # With bill client deal id
        bill.client_deal_id = "123B"
        bill.save()
        self.assertEqual(bill.client_deal_id, "123B")  # no inheritance, client_dead_id is already defined

        # With multiple mission
        mission2 = Mission(lead=lead, subsidiary_id=1)
        mission2.save()
        bill2 = ClientBill(lead=lead, creation_date=date(2010, 10, 5), state="1_SENT")
        bill2.save()
        bill2.client_deal_id = ""
        BillDetail(bill=bill2, mission=mission, quantity=1, unit_price=1000).save()
        BillDetail(bill=bill2, mission=mission2, quantity=1, unit_price=1000).save()
        bill2.save()
        self.assertEqual(bill2.client_deal_id, "123")  # multiple mission. Use lead client deal id

class TestBillingViews(TestCase):
    fixtures = PYDICI_FIXTURES
    def setUp(self):
        setup_test_user_features()
        self.test_user = User.objects.get(username=TEST_USERNAME)
    def test_create_client_bill(self):
        self.client.force_login(self.test_user)
        bill_count = ClientBill.objects.count()
        data = {
            "lead": 1,
            "state": "0_DRAFT",
            "lang": "fr-fr",
            "creation_date": date.today(),
            "due_date": date.today(),
            "vat": 20,
            "bill_id": 123
        }
        response = self.client.post(reverse("billing:client_bill"), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(bill_count + 1, ClientBill.objects.count())

        response = self.client.get(reverse("billing:bill_pdf", args=[ClientBill.objects.last().id,]))
        self.assertEqual(response.status_code, 200)

    def test_pre_billing(self):
        self.client.force_login(self.test_user)
        previous_month = previousMonth(date.today())
        lead = Lead.objects.get(id=1)
        c1 = Consultant.objects.get(id=1)
        c2 = Consultant.objects.get(id=2)
        c2.company_id = 2
        c2.save()
        mission = Mission(lead=lead, subsidiary_id=1, billing_mode="TIME_SPENT", nature="PROD", probability=100)
        mission.save()
        FinancialCondition(consultant=c1, mission=mission, daily_rate=800).save()
        FinancialCondition(consultant=c2, mission=mission, daily_rate=1100).save()

        # No timesheet, no pre billing
        r = self.client.get(reverse("billing:pre_billing"))
        self.assertFalse(r.context["internal_billing"])
        self.assertFalse(r.context["time_spent_billing"])

        # Add simple timesheet. Still no internal billing
        Timesheet(mission=mission, working_date=previous_month, consultant=c1, charge=7).save()
        r = self.client.get(reverse("billing:pre_billing"))
        self.assertFalse(r.context["internal_billing"])
        self.assertEqual(len(r.context["time_spent_billing"]), 1)

        # Timesheet from a consultant of another company, we have now internal billing
        Timesheet(mission=mission, working_date=previous_month, consultant=c2, charge=4).save()
        r = self.client.get(reverse("billing:pre_billing"))
        self.assertTrue(r.context["internal_billing"])
        self.assertEqual(len(r.context["time_spent_billing"]), 1)

        # In fact, this consultant is a subcontractor, not internal billing required
        c2.subcontractor = True
        c2.save()
        r = self.client.get(reverse("billing:pre_billing"))
        self.assertFalse(r.context["internal_billing"])
        self.assertEqual(len(r.context["time_spent_billing"]), 1)

class TestBillingUtils(TestCase):
    fixtures = PYDICI_FIXTURES
    def setUp(self):
        setup_test_user_features()
        self.test_user = User.objects.get(username=TEST_USERNAME)

    def test_get_client_billing_control_pivotable_data(self):
        c = Consultant.objects.get(id=1)
        c2 = Consultant.objects.get(id=2)
        d = json.loads(get_client_billing_control_pivotable_data())
        self.assertEqual(len(d), 13)  # Default test fixtures

        s = Subsidiary(name="test", code="T")
        s.save()
        d = json.loads(get_client_billing_control_pivotable_data(filter_on_subsidiary=s))
        self.assertEqual(len(d), 0)  # new subsidiary, empty set

        l = Lead(subsidiary=s, client_id=1)
        l.save()
        d = json.loads(get_client_billing_control_pivotable_data(filter_on_lead=l))
        self.assertEqual(len(d), 0)  # new lead, empty set

        m = Mission(lead=l, subsidiary=s, nature="PROD", probability=100, billing_mode="TIME_SPENT")
        m.save()
        FinancialCondition(consultant=c, mission=m, daily_rate=1000).save()
        self.assertEqual(len(d), 0)  # new mission but no timesheet, empty set

        Timesheet(mission=m, consultant=c, working_date=date.today(), charge=1).save()
        d = json.loads(get_client_billing_control_pivotable_data(filter_on_lead=l))
        self.assertEqual(len(d), 1)  # still no billing
        self.assertEqual(sum([x[_("amount")] for x in d]), 1000)

        # add client bill detail
        bill = ClientBill(lead=l, creation_date=date.today(), state="0_PROPOSED")
        bill.save()
        BillDetail(bill=bill, consultant=c, mission=m, quantity=1, unit_price=1000, month=date.today().replace(day=1)).save()
        d = json.loads(get_client_billing_control_pivotable_data(filter_on_lead=l))
        self.assertEqual(len(d), 2)  # 1 activity and 1 bill
        self.assertEqual(sum([x[_("amount")] for x in d]), 0)  # we billed what we did

        # add bills outside timesheet window and with wrong consultant
        BillDetail(bill=bill, consultant=c, mission=m, quantity=3, unit_price=1000, month=nextMonth(date.today())).save()
        BillDetail(bill=bill, consultant=c2, mission=m, quantity=4, unit_price=1000, month=previousMonth(date.today())).save()
        d = json.loads(get_client_billing_control_pivotable_data(filter_on_lead=l))
        self.assertEqual(len(d), 4)  # 2 + 2 new bills
        self.assertEqual(sum([x[_("amount")] for x in d]), -7000)  # we over bill by 7 * 1000

        # add timesheet according billing
        Timesheet(mission=m, consultant=c, working_date=nextMonth(date.today()), charge=3).save()
        Timesheet(mission=m, consultant=c, working_date=previousMonth(date.today()), charge=4).save()
        d = json.loads(get_client_billing_control_pivotable_data(filter_on_lead=l))
        self.assertEqual(len(d), 6)  # activity and bill for 3 months
        self.assertEqual(sum([x[_("amount")] for x in d]), 0)  # we billed what we did

        # And new, add a fixed price mission
        m2 = Mission(lead=l, subsidiary=s, nature="PROD", probability=100, price=5, billing_mode="FIXED_PRICE")
        m2.save()
        FinancialCondition(consultant=c, mission=m2, daily_rate=1000).save()
        BillDetail(bill=bill, mission=m2, quantity=1, unit_price=3000).save()
        d = json.loads(get_client_billing_control_pivotable_data(filter_on_lead=l))
        self.assertEqual(len(d), 7)  # activity and bill for 3 months and 1 fixed price bill
        self.assertEqual(sum([x[_("amount")] for x in d]), -3000) # we bill in advance

        # Add timesheet on fixed price mission
        Timesheet(mission=m2, consultant=c, working_date=date.today(), charge=2).save()
        d = json.loads(get_client_billing_control_pivotable_data(filter_on_lead=l))
        self.assertEqual(len(d), 8)  # 6 + and 1 activity and 1 bill for fixed price mission
        self.assertEqual(sum([x[_("amount")] for x in d]), -1000) # Still one day of advance

        # We spent too much time, but it won't be billed as it's a fixe price mission
        Timesheet(mission=m2, consultant=c, working_date=nextMonth(date.today()), charge=8).save()
        d = json.loads(get_client_billing_control_pivotable_data(filter_on_lead=l))
        self.assertEqual(len(d), 9)  # 6 + and 2 activities and 1 bill for fixed price mission
        self.assertEqual(sum([x[_("amount")] for x in d]), 2000)  # We should have 2K to bill, no more
