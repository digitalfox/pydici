# coding: utf-8
"""
Test cases for Expense module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from core.tests import PYDICI_FIXTURES
from expense.models import Expense, ExpenseCategory, ExpensePayment
from expense.utils import expense_next_states, can_edit_expense




class WorkflowTest(TestCase):
    """Test pydici workflows"""
    fixtures = PYDICI_FIXTURES

    def test_expense_swf(self):
        """Test expense simple & stupid workflow"""

        cache.clear()  # avoid user team cache
        tco = User.objects.get(username="tco")
        abr = User.objects.get(username="abr")
        fla = User.objects.get(username="fla")
        sre = User.objects.get(username="sre")
        gba = User.objects.get(username="gba")
        abo = User.objects.get(username="abo")

        category = ExpenseCategory.objects.create(name="repas")
        e = Expense.objects.create(user=tco, description="une grande bouffe",
                                   category=category, amount=123, chargeable=False,
                                   creation_date=date.today(), expense_date=date.today())

        # current (starting) state is requested
        self.assertEqual(e.state, "REQUESTED")
        self.assertEqual(len(expense_next_states(e, tco)), 0)  # No transition allowed for user
        self.assertEqual(len(expense_next_states(e, fla)), 0)  # No transition allowed for paymaster
        self.assertEqual(len(expense_next_states(e, gba)), 0)  # No transition allowed for administrator of other subsidiary

        # But for his manager or administrator
        for user in (abr, sre):
            states = expense_next_states(e, user)
            self.assertIn("VALIDATED", states)
            self.assertIn("NEEDS_INFORMATION", states)
            self.assertIn("REJECTED", states)

        # Not yet validated, so user can edit it
        self.assertTrue(can_edit_expense(e, tco))

        # Reject it
        e.state = "REJECT"
        e.save()
        for user in (tco, abr, fla, gba):
            self.assertEqual(len(expense_next_states(e, user)), 0)  # No transition allowed
            self.assertFalse(can_edit_expense(e, user))  # No edition allowed
        self.assertTrue(can_edit_expense(e, sre))  # Except admin

        # Validate it
        e.state = "VALIDATED"
        e.save()
        for user in (tco, abr):
            self.assertEqual(len(expense_next_states(e, user)), 0)  # No transition allowed
            self.assertFalse(can_edit_expense(e, user))  # No edition allowed
        # Except paymaster for control/ask info
        states = expense_next_states(e, fla)
        self.assertIn("NEEDS_INFORMATION", states)
        self.assertIn("CONTROLLED", states)
        self.assertTrue(can_edit_expense(e, sre))

        # Ask information
        e.state = "NEEDS_INFORMATION"
        e.save()
        self.assertTrue(can_edit_expense(e, tco))
        self.assertTrue(can_edit_expense(e, abr))

        # Control it
        e.state = "CONTROLLED"
        e.save()
        for user in (tco, abr, gba):
            self.assertEqual(len(expense_next_states(e, user)), 0)  # No transition allowed
            self.assertFalse(can_edit_expense(e, user))  # No edition allowed
        self.assertTrue(can_edit_expense(e, sre))  # Except admin
        e.corporate_card = True
        e.save()
        self.assertEqual(len(expense_next_states(e, fla)), 0)  # No payment if corporate card was used

        # Create a payment for that expense
        expensePayment = ExpensePayment(payment_date=date.today())
        expensePayment.save()
        e.expensePayment = expensePayment
        e.state = "PAID"
        e.save()
        self.assertEqual(expensePayment.user(), tco)
        self.assertEqual(expensePayment.amount(), 123)
        for user in (tco, abr, fla):
            self.assertEqual(len(expense_next_states(e, user)), 0)  # No transition allowed
            self.assertFalse(can_edit_expense(e, user))  # No edition allowed
        self.assertTrue(can_edit_expense(e, sre))  # Except admin

        # Create a new one in other subsidiary
        e = Expense.objects.create(user=abo, description="une belle quille de vin nature",
                                   category=category, amount=123, chargeable=False,
                                   creation_date=date.today(), expense_date=date.today())

        # gba is not his manager the subsidiary manager, so he should be able to manage its expense
        states = expense_next_states(e, gba)
        self.assertIn("VALIDATED", states)
        self.assertIn("NEEDS_INFORMATION", states)
        self.assertIn("REJECTED", states)

        e.state = "VALIDATED"
        for user in (abo, gba):
            self.assertEqual(len(expense_next_states(e, user)), 0)  # No transition allowed
            self.assertFalse(can_edit_expense(e, user))  # No edition allowed

