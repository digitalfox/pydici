# coding: utf-8
"""
Test cases for billing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.test import TestCase, TransactionTestCase
from django.db import IntegrityError

from crm.models import Supplier, Client
from billing.models import SupplierBill, ClientBill
from leads.models import Lead
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
        client = Client.objects.get(id=1)
        bill = ClientBill()
        self.assertEqual(bill.state, "0_DRAFT")
        self.assertRaises(Exception, bill.save)  # No lead, no client and no amount
        bill.lead = lead
        bill.client = client
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
