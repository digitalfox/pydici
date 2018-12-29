# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in Expense models or view.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)

Some words on expense workflow. Pydici used to use a fully customisable workflow
with the help of django_workflows module. It was discontinued. And after 10 years of used
the full power of a customisable workflow has never been used. The only change so far was the
addition of the controled state. Moreover, such a customisable workflow leads to some significant
drawbacks: poor performance, UI cumbersome due to generic approach and some functional limitation.
So the decision was to change this powerful but somewhat useless to a simple harcoded stupid workflow.
It rely on 6 states:
- requested: the first and starting state of any expense.
- validated: once review by user manager
- rejected: if any reviewer do not validate expense. This is a terminal state
- needs information: self explanatory, that's when user needs to provide missing info
- controled: second level review by administrative staff. This can be a terminal state if no payment is needed (ex. corp card)
- paid: expense has been paid to user (and linked to a payment). This is a terminal state

For groups control permissions around this simple workflow:
- expense_administrator: can do anything
- expense_manager: can validate requested expense of his team
- expense_paymaster: can control expense create expense payment
- expense_requester: can create new expense
"""

from django.core.cache import cache

from expense.models import EXPENSE_STATES
from people.models import Consultant


def expense_next_states(expense, user):
    """Allowed next states for this expense and given user"""
    state = expense.state
    next_states = ()

    # Get roles according to standard expense groups
    expense_administrator, expense_manager, expense_paymaster, expense_requester = user_expense_perm(user)

    # Get user team if any
    user_team = user_expense_team(user)

    # A user cannot manipulate his own expense, except admin
    if expense.user == user and not expense_administrator:
        return next_states

    if state == "REQUESTED":
        if expense_administrator:
            next_states = ("VALIDATED", "NEEDS_INFORMATION", "REJECTED")
        if expense.user in user_team and expense_manager:
            next_states = ("VALIDATED", "NEEDS_INFORMATION", "REJECTED")
    elif state == "VALIDATED":
        if expense_administrator or expense_paymaster:
            next_states = ("NEEDS_INFORMATION", "CONTROLLED")
    elif state == "NEEDS_INFORMATION":
        if expense_administrator or expense_paymaster:
            next_states = ("VALIDATED", "REJECTED", "REQUESTED")
        if expense.user == user and expense_requester:
            next_states = ("REQUESTED",)
    elif state == "CONTROLLED":
        if expense_administrator or expense_paymaster:
            if not expense.corporate_card:
                next_states = ("PAID",)

    allowed_states = [i[0] for i in EXPENSE_STATES]
    for state in next_states:
        assert state in allowed_states  # Just to be sure we don't mess up

    return next_states


def can_edit_expense(expense, user):
    """Check if user can modify given expense"""
    expense_administrator, expense_manager, expense_paymaster, expense_requester = user_expense_perm(user)

    if expense_administrator:
        return True

    if expense.state not in ("REQUESTED", "NEEDS_INFORMATION"):
        return False

    if expense.user == user:
        return True

    user_team = user_expense_team(user)

    if expense.user in user_team and expense_manager:
        return True

    # All other case, it's a no, sorry
    return False


def expense_state_display(state):
    d = dict(EXPENSE_STATES)
    return d.get(state, "??")


def user_expense_perm(user):
    """compute user perm and returns expense_administrator, expense_manager, expense_paymaster, expense_requester"""
    expense_administrator = user.is_superuser or user.groups.filter(name="expense_administrator").exists()
    expense_manager = expense_administrator or user.groups.filter(name="expense_manager").exists()
    expense_paymaster = expense_administrator or user.groups.filter(name="expense_paymaster").exists()
    expense_requester = expense_administrator or user.groups.filter(name="expense_requester").exists()

    return expense_administrator, expense_manager, expense_paymaster, expense_requester


def user_expense_team(user):
    EXPENSE_USER_TEAM_CACHE_KEY = "PYDICI_EXPENSE_USER_%s"
    try:
        consultant = Consultant.objects.get(trigramme__iexact=user.username)
        user_team = cache.get(EXPENSE_USER_TEAM_CACHE_KEY % consultant.id)
        if not user_team:
            user_team = consultant.userTeam(excludeSelf=False)
            cache.set(EXPENSE_USER_TEAM_CACHE_KEY % consultant.id, user_team, 3600)
    except Consultant.DoesNotExist:
        user_team = []
    return user_team