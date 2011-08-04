# coding: utf-8
"""
Expense module utils functions
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""


import workflows.utils as wf
from pydici.expense.models import Expense

def get_user_expenses(user):
    """Returns user expenses still in the workflow as a list of triplet :
    (expense, state, list of allowed transitions)
    list of transitions is always none for user expenses"""
    expenses = Expense.objects.filter(user=user, workflow_in_progress=True).select_related()
    return [(e, wf.get_state(e), None) for e in expenses]

def get_team_expenses(user, team):
    """Returns user team expenses still in the workflow as a list of triplet :
    (expense, state, list of allowed transitions)
    @param user: team responsible user
    @param team: list of user object"""
    expenses = Expense.objects.filter(user__in=team, workflow_in_progress=True).order_by("user").select_related()
    return [(e, wf.get_state(e), wf.get_allowed_transitions(e, user)) for e in expenses]
