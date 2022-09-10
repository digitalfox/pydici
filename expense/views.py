# coding: utf-8
"""
Pydici expense views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date
import json
from io import BytesIO
import decimal

from django_tables2 import RequestConfig

from django.http import HttpResponseRedirect, HttpResponse, Http404, HttpResponseForbidden
from django.utils.translation import gettext as _
from django.urls import reverse
from django.db.models import Q, Count
from django.shortcuts import render, redirect
from django.contrib import messages

from expense.forms import ExpenseForm, ExpensePaymentForm
from expense.models import Expense, ExpensePayment
from expense.tables import ExpenseTable, UserExpenseWorkflowTable, ManagedExpenseWorkflowTable
from leads.models import Lead
from people.models import Consultant
from core.decorator import pydici_non_public, pydici_feature, pydici_subcontractor
from core.views import tableToCSV
from expense.utils import expense_next_states, can_edit_expense, in_terminal_state, user_expense_perm
from people.utils import users_are_in_same_company


@pydici_subcontractor
@pydici_feature("expense")
def expense(request, expense_id):
    """Display one expense"""
    expense_administrator, expense_subsidiary_manager, expense_manager, expense_paymaster, expense_requester = user_expense_perm(request.user)

    if not expense_requester:
        return HttpResponseRedirect(reverse("core:forbidden"))

    consultant = Consultant.objects.get(trigramme__iexact=request.user.username)
    user_team = consultant.user_team(exclude_self=False)

    try:
        expense = Expense.objects.get(id=expense_id)
    except Expense.DoesNotExist:
        raise Http404

    if not (expense_administrator or expense_paymaster):
        if not (expense.user == request.user or
                expense.user in user_team or
                (expense_subsidiary_manager and users_are_in_same_company(expense.user, request.user))):
            return HttpResponseRedirect(reverse("core:forbidden"))

    return render(request, "expense/expense.html",
                  {"expense": expense,
                   "can_edit": can_edit_expense(expense, request.user),
                   "can_edit_vat": expense_administrator or expense_paymaster,
                   "user": request.user})


@pydici_subcontractor
@pydici_feature("expense")
def expenses(request, expense_id=None, clone_from=None):
    """Display user expenses and expenses that he can validate"""
    expense_administrator, expense_subsidiary_manager, expense_manager, expense_paymaster, expense_requester = user_expense_perm(request.user)

    if not expense_requester:
        return HttpResponseRedirect(reverse("core:forbidden"))

    consultant = Consultant.objects.get(trigramme__iexact=request.user.username)
    subcontractor = None
    if consultant.subcontractor:
        subcontractor = consultant

    if expense_subsidiary_manager:
        # consider all subsidiary for expense subsidiary manager
        user_team = consultant.user_team(subsidiary=True, exclude_self=True)
    else:
        user_team = consultant.user_team(exclude_self=True)

    try:
        if expense_id:
            expense = Expense.objects.get(id=expense_id)
            if not can_edit_expense(expense, request.user):
                messages.add_message(request, messages.WARNING, _("You are not allowed to edit that expense"))
                expense_id = None
                expense = None
    except Expense.DoesNotExist:
        messages.add_message(request, messages.ERROR, _("Expense %s does not exist" % expense_id))
        expense_id = None

    if request.method == "POST":
        if expense_id:
            form = ExpenseForm(request.POST, request.FILES, instance=expense, subcontractor=subcontractor)
        else:
            form = ExpenseForm(request.POST, request.FILES, subcontractor=subcontractor)
        if form.is_valid():
            expense = form.save(commit=False)
            if not hasattr(expense, "user"):
                # Don't update user if defined (case of expense updated by manager or administrator)
                expense.user = request.user
            expense.state = "REQUESTED"
            expense.workflow_in_progress = True
            expense.save()
            return HttpResponseRedirect(reverse("expense:expenses"))
    else:
        if expense_id:
            form = ExpenseForm(instance=expense, subcontractor=subcontractor)  # A form that edit current expense
        elif clone_from:
            try:
                expense = Expense.objects.get(id=clone_from)
                expense.pk = None  # Null pk so it will generate a new fresh object during form submit
                expense.receipt = None  # Never duplicate the receipt, a new one need to be provided
                form = ExpenseForm(instance=expense, subcontractor=subcontractor)  # A form with the new cloned expense (not saved)
            except Expense.DoesNotExist:
                form = ExpenseForm(initial={"expense_date": date.today()})  # An unbound form
        else:
            form = ExpenseForm(initial={"expense_date": date.today()}, subcontractor=subcontractor)  # An unbound form

    # Get user expenses
    user_expenses = Expense.objects.filter(user=request.user, workflow_in_progress=True).select_related()

    if user_team:
        team_expenses = Expense.objects.filter(user__in=user_team, workflow_in_progress=True).select_related()
    else:
        team_expenses = []

    if expense_administrator: # Admin manage all expenses
        managed_expenses = Expense.objects.filter(workflow_in_progress=True).select_related()
    elif expense_paymaster: # Paymaster manage all expenses except his own
        managed_expenses = Expense.objects.filter(workflow_in_progress=True).exclude(user=request.user).select_related()
    else:
        managed_expenses = team_expenses

    userExpenseTable = UserExpenseWorkflowTable(user_expenses)
    userExpenseTable.transitionsData = dict([(e.id, []) for e in user_expenses])  # Inject expense allowed transitions. Always empty for own expense
    userExpenseTable.expenseEditPerm = dict([(e.id, can_edit_expense(e, request.user)) for e in user_expenses])  # Inject expense edit permissions
    RequestConfig(request, paginate={"per_page": 50}).configure(userExpenseTable)

    managedExpenseTable = ManagedExpenseWorkflowTable(managed_expenses)
    managedExpenseTable.transitionsData = dict([(e.id, expense_next_states(e, request.user)) for e in managed_expenses])  # Inject expense allowed transitions
    managedExpenseTable.expenseEditPerm = dict([(e.id, can_edit_expense(e, request.user)) for e in managed_expenses])  # Inject expense edit permissions
    RequestConfig(request, paginate={"per_page": 100}).configure(managedExpenseTable)
    return render(request, "expense/expenses.html",
                  {"user_expense_table": userExpenseTable,
                   "managed_expense_table": managedExpenseTable,
                   "modify_expense": bool(expense_id),
                   "form": form,
                   "user": request.user})


@pydici_subcontractor
@pydici_feature("expense")
def expense_receipt(request, expense_id):
    """Returns expense receipt if authorize to"""
    data = BytesIO()
    expense_administrator, expense_subsidiary_manager, expense_manager, expense_paymaster, expense_requester = user_expense_perm(request.user)
    try:
        expense = Expense.objects.get(id=expense_id)
        content_type = expense.receipt_content_type()
        if expense.user == request.user or\
           expense_manager or expense_paymaster or expense_administrator:
            data = expense.receipt_data()
    except (Expense.DoesNotExist, OSError):
        pass

    return HttpResponse(data)


@pydici_subcontractor
@pydici_feature("expense")
def expense_delete(request, expense_id):
    """Delete given expense if authorized to"""
    expense = None
    expense_administrator, expense_subsidiary_manager, expense_manager, expense_paymaster, expense_requester = user_expense_perm(request.user)
    if not expense_requester:
        return HttpResponseRedirect(reverse("core:forbidden"))

    try:
        if expense_id:
            expense = Expense.objects.get(id=expense_id)
            if not can_edit_expense(expense, request.user):
                messages.add_message(request, messages.WARNING, _("You are not allowed to edit that expense"))
                expense_id = None
                expense = None
    except Expense.DoesNotExist:
        messages.add_message(request, messages.ERROR, _("Expense %s does not exist" % expense_id))
        expense_id = None

    if expense:
        expense.delete()
        messages.add_message(request, messages.INFO, _("Expense %s has been deleted" % expense_id))

    # Redirect user to expense main page
    return redirect("expense:expenses")


@pydici_subcontractor
@pydici_feature("expense")
def expenses_history(request):
    """Display expense history"""

    expense_administrator, expense_subsidiary_manager, expense_manager, expense_paymaster, expense_requester = user_expense_perm(request.user)

    return render(request, "expense/expense_archive.html",
                  {"data_url": reverse('expense:expense_table_DT'),
                   "data_options": ''' "pageLength": 25,
                                       "order": [[0, "desc"]],
                                       "columnDefs": [{ "orderable": false, "targets": [6,] },
                                                      { className: "hidden-xs hidden-sm hidden-md", "targets": [2, 10, 12, 13]},
                                                      { className: "description", "targets": [3]},
                                                      { className: "amount", "targets": [5]}],
                                       "fnDrawCallback": function( oSettings ) {make_vat_editable(); }''',
                   "can_edit_vat": expense_administrator or expense_paymaster,
                   "user": request.user})


@pydici_non_public
def lead_expenses(request, lead_id):
    """Page fragment or csv that display expenses related to given lead"""
    try:
        lead = Lead.objects.get(id=lead_id)
        expenses = Expense.objects.filter(lead=lead).select_related().prefetch_related("clientbill_set")
    except Lead.DoesNotExist:
        expenses = []
        lead = None
    return render(request, "expense/expense_list.html",
                  {"expenses": expenses,
                   "lead": lead,
                   "user": request.user})


@pydici_non_public
@pydici_feature("reports")
def chargeable_expenses(request):
    """Display all chargeable expenses that are not yet charged in a bill"""
    expenses= Expense.objects.filter(chargeable=True)
    expenses = expenses.annotate(Count("clientbill"), Count("billexpense"))
    expenses = expenses.filter(clientbill__count=0, billexpense__count=0)
    expenses = expenses.select_related("lead__client__organisation__company").prefetch_related("clientbill_set")
    return render(request, "expense/chargeable_expenses.html",
                  {"expenses": expenses,
                   "user": request.user})


@pydici_non_public
@pydici_feature("reports")
def update_expense_state(request, expense_id, target_state):
    """Do workflow transition for that expense."""
    error = False
    message = ""

    try:
        expense = Expense.objects.get(id=expense_id)
    except Expense.DoesNotExist:
        message = _("Expense %s does not exist" % expense_id)
        error = True

    if not error:
        next_states = expense_next_states(expense, request.user)
        if target_state in next_states:
            expense.state = target_state
            if in_terminal_state(expense):
                expense.workflow_in_progress = False
            expense.save()
            message = _("Successfully update expense")
        else:
            message = ("Transition %s is not allowed" % target_state)
            error = True

    response = {"message": message,
                "expense_id": expense_id,
                "error": error}

    return HttpResponse(json.dumps(response), content_type="application/json")


@pydici_non_public
@pydici_feature("management")
def update_expense_vat(request):
    """Update expense VAT."""

    expense_administrator, expense_subsidiary_manager, expense_manager, expense_paymaster, expense_requester = user_expense_perm(request.user)

    if not (expense_administrator or expense_paymaster):
        return HttpResponseForbidden()

    try:
        expense_id = request.POST["id"]
        value = request.POST["value"].replace(",", ".")
        expense = Expense.objects.get(id=expense_id)
        expense.vat = decimal.Decimal(value)
        expense.save()
        message = value
    except Expense.DoesNotExist:
        message = _("Expense %s does not exist" % expense_id)
    except (ValueError, decimal.InvalidOperation):
        message = _("Incorrect value")

    return HttpResponse(message)


@pydici_non_public
@pydici_feature("management")
def expense_payments(request, expense_payment_id=None):
    readOnly = False
    expense_administrator, expense_subsidiary_manager, expense_manager, expense_paymaster, expense_requester = user_expense_perm(request.user)

    if not (expense_paymaster or expense_administrator):
        readOnly = True

    try:
        if expense_payment_id:
            expensePayment = ExpensePayment.objects.get(id=expense_payment_id)
    except ExpensePayment.DoesNotExist:
        messages.add_message(request, messages.ERROR, _("Expense payment %s does not exist" % expense_payment_id))
        expense_payment_id = None
        expensePayment = None

    if readOnly:
        expensesToPay = []
    else:
        expensesToPay = Expense.objects.filter(workflow_in_progress=True, corporate_card=False, expensePayment=None, state="CONTROLLED")

    if request.method == "POST":
        if readOnly:
            # A bad user is playing with urls...
            return HttpResponseRedirect(reverse("core:forbidden"))
        form = ExpensePaymentForm(request.POST)
        if form.is_valid():
            if expense_payment_id:
                expensePayment = ExpensePayment.objects.get(id=expense_payment_id)
                expensePayment.payment_date = form.cleaned_data["payment_date"]
            else:
                expensePayment = ExpensePayment(payment_date=form.cleaned_data["payment_date"])
            expensePayment.save()
            for expense in Expense.objects.filter(expensePayment=expensePayment):
                expense.expensePayment = None  # Remove any previous association
                expense.save()
            if form.cleaned_data["expenses"]:
                for expense in form.cleaned_data["expenses"]:
                    expense.expensePayment = expensePayment
                    expense.workflow_in_progress = False
                    expense.save()
            return HttpResponseRedirect(reverse("expense:expense_payments"))
        else:
            print("form is not valid")

    else:
        if expense_payment_id:
            expensePayment = ExpensePayment.objects.get(id=expense_payment_id)
            form = ExpensePaymentForm({"expenses": list(Expense.objects.filter(expensePayment=expensePayment).values_list("id", flat=True)), "payment_date": expensePayment.payment_date})  # A form that edit current expense payment
        else:
            form = ExpensePaymentForm(initial={"payment_date": date.today()})  # An unbound form

    return render(request, "expense/expense_payments.html",
                  {"modify_expense_payment": bool(expense_payment_id),
                   "data_url": reverse('expense:expense_payment_table_DT'),
                   "data_options": ''' "pageLength": 25,
                        "order": [[0, "desc"]],
                        "columnDefs": [{ "orderable": false, "targets": [1, 2, 4] }]''',
                   "expense_to_pay_table": ExpenseTable(expensesToPay),
                   "read_only": readOnly,
                   "can_edit_vat": expense_administrator or expense_paymaster,
                   "form": form,
                   "user": request.user})


@pydici_non_public
@pydici_feature("management")
def expense_payment_detail(request, expense_payment_id):
    """Display detail of this expense payment"""
    expense_administrator, expense_subsidiary_manager, expense_manager, expense_paymaster, expense_requester = user_expense_perm(request.user)
    if not expense_requester:
        return HttpResponseRedirect(reverse("core:forbidden"))
    try:
        if expense_payment_id:
            expensePayment = ExpensePayment.objects.get(id=expense_payment_id)
        if not (expensePayment.user() == request.user or expense_paymaster or expense_administrator):
            return HttpResponseRedirect(reverse("core:forbidden"))

    except ExpensePayment.DoesNotExist:
        messages.add_message(request, messages.ERROR, _("Expense payment %s does not exist" % expense_payment_id))
        return redirect("expense:expense_payments")

    return render(request, "expense/expense_payment_detail.html",
                  {"expense_payment": expensePayment,
                   "expense_table": ExpenseTable(expensePayment.expense_set.all()),
                   "can_edit_vat": expense_administrator or expense_paymaster,
                   "user": request.user})
