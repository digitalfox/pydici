# coding: utf-8
"""
Expense module utils functions
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""


import workflows.utils as wf
from pydici.expense.models import Expense

def get_user_expenses(user, only_in_workflow=True):
    """Returns user expenses still in the workflow as a list of triplet :
    (expense, state, list of allowed transitions)
    list of transitions is always none for user expenses
    @param only_in_workflow: only get expense in an active workflow"""
    expenses = Expense.objects.filter(user=user)
    if only_in_workflow:
        expenses = expenses.filter(workflow_in_progress=True)
    expenses = expenses.select_related()
    return [(e, wf.get_state(e), None) for e in expenses]

def get_team_expenses(user, team, no_transition=False, only_in_workflow=True):
    """Returns user team expenses still in the workflow as a list of triplet :
    (expense, state, list of allowed transitions)
    @param user: team responsible user
    @param team: list of user object
    @param no_transition: don't compute allowed transitions (default is false, ie. compute transition)
    @param only_in_workflow: only get expense in an active workflow"""
    expenses = Expense.objects.filter(user__in=team)
    if only_in_workflow:
        expenses = expenses.filter(workflow_in_progress=True)
    expenses = expenses.order_by("user").select_related()
    return [(e, wf.get_state(e), no_transition or wf.get_allowed_transitions(e, user)) for e in expenses]
