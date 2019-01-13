# coding: utf-8
"""
Test cases for Expense module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from core.tests import PYDICI_FIXTURES
from expense.models import Expense, ExpenseCategory, ExpensePayment
from expense.utils import expense_next_states, can_edit_expense




class WorkflowTest(TestCase):
    """Test pydici workflows"""
    fixtures = PYDICI_FIXTURES

    def test_expense_swf(self):
        """Test expense simple & stupid workflow"""

        tco = User.objects.get(username="tco")
        abr = User.objects.get(username="abr")
        fla = User.objects.get(username="fla")
        sre = User.objects.get(username="sre")

        category = ExpenseCategory.objects.create(name="repas")
        e = Expense.objects.create(user=tco, description="une grande bouffe",
                                   category=category, amount=123, chargeable=False,
                                   creation_date=date.today(), expense_date=date.today())

        # current (starting) state is requested
        self.assertEqual(e.state, "REQUESTED")
        self.assertEqual(len(expense_next_states(e, tco)), 0)  # No transition allowed for user
        self.assertEqual(len(expense_next_states(e, fla)), 0)  # No transition allowed for paymaster
        # But for his manager...
        states = expense_next_states(e, abr)
        self.assertIn("VALIDATED", states)
        self.assertIn("NEEDS_INFORMATION", states)
        self.assertIn("REJECTED", states)
        self.assertTrue(can_edit_expense(e, tco))

        # Reject it
        e.state = "REJECT"
        e.save()
        for user in (tco, abr, fla):
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
        for user in (tco, abr):
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