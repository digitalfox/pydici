# coding: utf-8
"""
Pydici expense views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from datetime import date, timedelta
import workflows.utils as wf
import permissions.utils as perm
from workflows.models import Transition

from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.contrib.auth.decorators import permission_required, login_required
from django.utils.translation import ugettext as _
from django.core import urlresolvers
from django.template import RequestContext

from pydici.expense.forms import ExpenseForm
from pydici.expense.models import Expense
from pydici.people.models import Consultant

@login_required
def expenses(request, expense_id=None):
    """Display user expenses and expenses that he can validate"""

    try:
        consultant = Consultant.objects.get(trigramme__iexact=request.user.username)
        user_team = consultant.userTeam()
    except Consultant.DoesNotExist:
        user_team = []

    try:
        if expense_id:
            expense = Expense.objects.get(id=expense_id)
            if not (perm.has_permission(expense, request.user, "expense_edit")
                    and (expense.user == request.user or expense.user in user_team)):
                request.user.message_set.create(message=_("You are not allowed to edit that expense"))
                expense_id = None
                expense = None
    except Expense.DoesNotExist:
        request.user.message_set.create(message=_("Expense %s does not exist" % expense_id))
        expense_id = None

    if request.method == "POST":
        if expense_id:
            form = ExpenseForm(request.POST, request.FILES, instance=expense)
        else:
            form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            print request.FILES
            expense = form.save(commit=False)
            expense.user = request.user
            expense.creation_date = date.today()
            expense.save()
            wf.set_initial_state(expense)
            return HttpResponseRedirect(urlresolvers.reverse("pydici.expense.views.expenses"))
    else:
        if expense_id:
            form = ExpenseForm(instance=expense) # A form that edit current expense
        else:
            form = ExpenseForm() # An unbound form        

    # Get user expenses
    user_expenses = Expense.objects.filter(user=request.user, workflow_in_progress=True)
    user_expenses = user_expenses.select_related()

    if user_team:
        team_expenses = Expense.objects.filter(user__in=user_team, workflow_in_progress=True)
        team_expenses = team_expenses.order_by("user").select_related()
    else:
        team_expenses = []

    # Get managed expense for paymaster only
    managed_expenses = []
    if perm.has_role(request.user, "expense paymaster"):
        for managed_expense in Expense.objects.filter(workflow_in_progress=True).exclude(user=request.user):
            if managed_expense in team_expenses:
                continue
            transitions = wf.get_allowed_transitions(managed_expense, request.user)
            if transitions:
                managed_expenses.append((managed_expense, wf.get_state(managed_expense), transitions))

    # Add state and allowed transitions
    user_expenses = [(e, wf.get_state(e), None) for e in user_expenses] # Don't compute transition for user as no one is available
    team_expenses = [(e, wf.get_state(e), wf.get_allowed_transitions(e, request.user)) for e in team_expenses]

    # Concatenate managed and team expenses
    managed_expenses = team_expenses + managed_expenses

    # Sort expenses
    #TODO: sort expenses on user,state,date

    # Prune old expense in terminal state (no more transition)
    for expense in Expense.objects.filter(workflow_in_progress=True, update_date__lt=(date.today() - timedelta(30))):
        if wf.get_state(expense).transitions.count() == 0:
            expense.workflow_in_progress = False

    return render_to_response("expense/expenses.html",
                              {"user_expenses" : user_expenses,
                               "managed_expenses" : managed_expenses,
                               "modify_expense" : bool(expense_id),
                               "form" : form,
                               "user": request.user },
                               RequestContext(request))

def update_expense_state(request, expense_id, transition_id):
    """Do workflow transition for that expense"""
    try:
        expense = Expense.objects.get(id=expense_id)
        if expense.user == request.user and not perm.has_role(request.user, "expense administrator"):
            request.user.message_set.create(message=_("You cannot manage your own expense !"))
            return HttpResponseRedirect(urlresolvers.reverse("pydici.expense.views.expenses"))
    except Expense.DoesNotExist:
        request.user.message_set.create(message=_("Expense %s does not exist" % expense_id))
        return HttpResponseRedirect(urlresolvers.reverse("pydici.expense.views.expenses"))
    try:
        transition = Transition.objects.get(id=transition_id)
    except Transition.DoesNotExist:
        request.user.message_set.create(message=_("Transition %s does not exist" % transition_id))
        return HttpResponseRedirect(urlresolvers.reverse("pydici.expense.views.expenses"))

    if wf.do_transition(expense, transition, request.user):
        request.user.message_set.create(message=_("Successfully update expense"))
    else:
        request.user.message_set.create(message=_("You cannot do this transition"))
    return HttpResponseRedirect(urlresolvers.reverse("pydici.expense.views.expenses"))
