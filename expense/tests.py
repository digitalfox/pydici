# coding: utf-8
"""
Test cases for Expense module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib.auth.models import User
from django.test import TestCase

from core.tests import PYDICI_FIXTURES
from people.models import Consultant
from expense.models import Expense, ExpenseCategory, ExpensePayment
from expense.default_workflows import install_expense_workflow


import workflows.utils as wf
import permissions.utils as perm
from workflows.models import Transition

from datetime import date


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