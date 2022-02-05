# coding: utf-8
"""
Test cases for billing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.test import TestCase, TransactionTestCase
from django.db import IntegrityError

from crm.models import Supplier, Client
from billing.models import SupplierBill, ClientBill, BillDetail
from leads.models import Lead
from staffing.models import Timesheet
from people.models import Consultant
from core.tests import PYDICI_FIXTURES

from datetime import date


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
        #TODO: add billDetail test
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





