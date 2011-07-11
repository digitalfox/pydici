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
from django.contrib.auth.decorators import permission_required
from django.utils.translation import ugettext as _
from django.core import urlresolvers
from django.template import RequestContext

from pydici.expense.forms import ExpenseForm
from pydici.expense.models import Expense
from pydici.people.models import Consultant


def expenses(request, expense_id=None):
    """Display user expenses and expenses that he can validate"""
    consultant = Consultant.objects.get(trigramme__iexact=request.user.username)

    try:
        if expense_id:
            expense = Expense.objects.get(id=expense_id)
            if not (perm.has_permission(expense, request.user, "expense_edit") and expense.consultant == consultant):
                request.user.message_set.create(message=_("You are not allowed to edit that expense"))
                expense_id = None
                expense = None
    except Expense.DoesNotExist:
        request.user.message_set.create(message=_("Expense %s does not exist" % expense_id))
        expense_id = None

    if request.method == "POST":
        if expense_id:
            form = ExpenseForm(request.POST, instance=expense)
        else:
            form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.consultant = consultant
            expense.creation_date = date.today()
            expense.save()
            wf.set_initial_state(expense)
            return HttpResponseRedirect(urlresolvers.reverse("pydici.expense.views.expenses"))
    else:
        if expense_id:
            form = ExpenseForm(instance=expense) # A form that edit current expense
        else:
            form = ExpenseForm() # An unbound form        

    user_expenses = Expense.objects.filter(consultant=consultant, workflow_in_progress=True)
    user_expenses = user_expenses.select_related()
    team = Consultant.objects.filter(manager=consultant).exclude(consultant=consultant)
    team_expenses = Expense.objects.filter(consultant__in=team, workflow_in_progress=True)
    team_expenses = team_expenses.order_by("consultant").select_related()

    # Add state and allowed transitions    
    user_expenses = [(e, wf.get_state(e), wf.get_allowed_transitions(e, request.user)) for e in user_expenses]
    team_expenses = [(e, wf.get_state(e), wf.get_allowed_transitions(e, request.user)) for e in team_expenses]

    # Prune old expense in terminal state (no more transition)
    for expense in Expense.objects.filter(workflow_in_progress=True, update_date__lt=(date.today() - timedelta(30))):
        if wf.get_state(expense).transitions.count() == 0:
            expense.workflow_in_progress = False

    return render_to_response("expense/expenses.html",
                              {"user_expenses" : user_expenses,
                               "team_expenses" : team_expenses,
                               "modify_expense" : bool(expense_id),
                               "form" : form,
                               "user": request.user },
                               RequestContext(request))

def update_expense_state(request, expense_id, transition_id):
    """Do workflow transition for that expense"""
    try:
        expense = Expense.objects.get(id=expense_id)
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
