# coding: utf-8
"""
Pydici expense views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta
import mimetypes
import workflows.utils as wf
import permissions.utils as perm
from workflows.models import Transition
from django_tables2 import RequestConfig

from django.http import HttpResponseRedirect, HttpResponse
from django.utils.translation import ugettext as _
from django.core import urlresolvers
from django.db.models import Q
from django.shortcuts import render
from django.contrib import messages


from expense.forms import ExpenseForm
from expense.models import Expense
from expense.tables import ExpenseTable, UserExpenseWorkflowTable, ManagedExpenseWorkflowTable
from people.models import Consultant
from staffing.models import Mission
from core.decorator import pydici_non_public
from core.views import tableToCSV


@pydici_non_public
def expenses(request, expense_id=None):
    """Display user expenses and expenses that he can validate"""
    if not request.user.groups.filter(name="expense_requester").exists():
        return HttpResponseRedirect(urlresolvers.reverse("forbiden"))
    try:
        consultant = Consultant.objects.get(trigramme__iexact=request.user.username)
        user_team = consultant.userTeam(excludeSelf=False)
    except Consultant.DoesNotExist:
        user_team = []

    try:
        if expense_id:
            expense = Expense.objects.get(id=expense_id)
            if not (perm.has_permission(expense, request.user, "expense_edit")
                    and (expense.user == request.user or expense.user in user_team)):
                messages.add_message(request, messages.WARNING, _("You are not allowed to edit that expense"))
                expense_id = None
                expense = None
    except Expense.DoesNotExist:
        messages.add_message(request, messages.ERROR, _("Expense %s does not exist" % expense_id))
        expense_id = None

    if request.method == "POST":
        if expense_id:
            form = ExpenseForm(request.POST, request.FILES, instance=expense)
        else:
            form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save(commit=False)
            if not hasattr(expense, "user"):
                # Don't update user if defined (case of expense updated by manager or adminstrator)
                expense.user = request.user
            expense.creation_date = date.today()
            expense.save()
            wf.set_initial_state(expense)
            return HttpResponseRedirect(urlresolvers.reverse("expense.views.expenses"))
    else:
        if expense_id:
            form = ExpenseForm(instance=expense)  # A form that edit current expense
        else:
            form = ExpenseForm(initial={"expense_date": date.today()})  # An unbound form

    # Get user expenses
    user_expenses = Expense.objects.filter(user=request.user, workflow_in_progress=True).select_related()

    if user_team:
        team_expenses = Expense.objects.filter(user__in=user_team, workflow_in_progress=True).select_related()
    else:
        team_expenses = []

    # Paymaster manage all expenses
    if perm.has_role(request.user, "expense paymaster"):
        managed_expenses = Expense.objects.filter(workflow_in_progress=True).exclude(user=request.user).select_related()
    else:
        managed_expenses = team_expenses

    userExpenseTable = UserExpenseWorkflowTable(user_expenses)
    userExpenseTable.transitionsData = dict([(e.id, []) for e in user_expenses])  # Inject expense allowed transitions. Always empty for own expense
    userExpenseTable.expenseEditPerm = dict([(e.id, perm.has_permission(e, request.user, "expense_edit")) for e in user_expenses])  # Inject expense edit permissions
    RequestConfig(request, paginate={"per_page": 50}).configure(userExpenseTable)

    managedExpenseTable = ManagedExpenseWorkflowTable(managed_expenses)
    managedExpenseTable.transitionsData = dict([(e.id, e.transitions(request.user)) for e in managed_expenses])  # Inject expense allowed transitions
    managedExpenseTable.expenseEditPerm = dict([(e.id, perm.has_permission(e, request.user, "expense_edit")) for e in managed_expenses])  # Inject expense edit permissions
    RequestConfig(request, paginate={"per_page": 50}).configure(managedExpenseTable)

    # Prune old expense in terminal state (no more transition)
    for expense in Expense.objects.filter(workflow_in_progress=True, update_date__lt=(date.today() - timedelta(30))):
        if wf.get_state(expense).transitions.count() == 0:
            expense.workflow_in_progress = False
            expense.save()

    return render(request, "expense/expenses.html",
                  {"user_expense_table": userExpenseTable,
                   "managed_expense_table": managedExpenseTable,
                   "modify_expense": bool(expense_id),
                   "form": form,
                   "user": request.user})


@pydici_non_public
def expense_receipt(request, expense_id):
    """Returns expense receipt if authorize to"""
    response = HttpResponse()
    try:
        expense = Expense.objects.get(id=expense_id)
        if expense.user == request.user or\
           perm.has_role(request.user, "expense paymaster") or\
           perm.has_role(request.user, "expense manager"):
            if expense.receipt:
                response['Content-Type'] = mimetypes.guess_type(expense.receipt.name)[0] or "application/stream"
                for chunk in expense.receipt.chunks():
                    response.write(chunk)
    except (Expense.DoesNotExist, OSError):
        pass

    return response


@pydici_non_public
def expenses_history(request):
    """Display expense history.
    @param year: year of history. If None, display recent items and year index"""
    expenses = Expense.objects.all().select_related().prefetch_related("clientbill_set", "user", "lead")
    try:
        consultant = Consultant.objects.get(trigramme__iexact=request.user.username)
        user_team = consultant.userTeam()
    except Consultant.DoesNotExist:
        user_team = []

    if not perm.has_role(request.user, "expense paymaster"):
        expenses = expenses.filter(Q(user=request.user) | Q(user__in=user_team))

    expenses = expenses.order_by("-expense_date")
    expenseTable = ExpenseTable(expenses)
    RequestConfig(request, paginate={"per_page": 100}).configure(expenseTable)

    if "csv" in request.GET:
        return tableToCSV(expenseTable, filename="expenses.csv")

    return render(request, "expense/expense_archive.html",
                  {"expense_table": expenseTable,
                   "user": request.user})


@pydici_non_public
def mission_expenses(request, mission_id):
    """Page fragment that display expenses related to given mission"""
    try:
        mission = Mission.objects.get(id=mission_id)
        if mission.lead:
            expenses = Expense.objects.filter(lead=mission.lead)
        else:
            expenses = []
    except Mission.DoesNotExist:
        expenses = []
    return render(request, "expense/expense_list.html",
                  {"expenses": expenses,
                   "user": request.user})


@pydici_non_public
def update_expense_state(request, expense_id, transition_id):
    """Do workflow transition for that expense"""
    redirect = HttpResponseRedirect(urlresolvers.reverse("expense.views.expenses"))
    try:
        expense = Expense.objects.get(id=expense_id)
        if expense.user == request.user and not perm.has_role(request.user, "expense administrator"):
            messages.add_message(request, messages.WARNING, _("You cannot manage your own expense !"))
            return redirect
    except Expense.DoesNotExist:
        messages.add_message(request, messages.WARNING, _("Expense %s does not exist" % expense_id))
        return redirect
    try:
        transition = Transition.objects.get(id=transition_id)
    except Transition.DoesNotExist:
        messages.add_message(request, messages.ERROR, _("Transition %s does not exist" % transition_id))
        return redirect

    if wf.do_transition(expense, transition, request.user):
        messages.add_message(request, messages.SUCCESS, _("Successfully update expense"))
    else:
        messages.add_message(request, messages.ERROR, _("You cannot do this transition"))
    return redirect
