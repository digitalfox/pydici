# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in People models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import datetime

from django.db.models import Count, Min
from django.utils.translation import ugettext as _
from django.urls import reverse

from people.models import Consultant
from crm.models import Subsidiary
from billing.models import ClientBill, SupplierBill
from expense.models import Expense
from expense.utils import user_expense_team


def get_scopes(subsidiary, team, target="all"):
    """Define scopes than can be used to filter data. Either team, subsidiary or everybody (default). Format is (type, filter, label) where type is "team_id" or "subsidiary_id".
    @:param
    @:param team
    @:param target: all (default), subsidiary or team
    @:param include_team: True (default), include team in scope
    @:return: scopes, scope_current_filter, scope_current_url_filter"""

    # Gather scopes
    scopes = [(None, "all", _(u"Everybody")), ]

    if target in ("all", "subsidiary"):
        for s in Subsidiary.objects.filter(consultant__active=True, consultant__subcontractor=False,
                                           consultant__productive=True).annotate(num=Count('consultant')).filter(num__gt=0):
            scopes.append(("subsidiary_id", "subsidiary_id=%s" % s.id, str(s)))

    if target in ("all", "team"):
        for manager_id, manager_name in Consultant.objects.filter(active=True, productive=True,
                                                                  subcontractor=False).values_list("staffing_manager",
                                                                                                   "staffing_manager__name").order_by().distinct():
            scopes.append(
                ("team_id", "team_id=%s" % manager_id, _(u"team %(manager_name)s") % {"manager_name": manager_name}))
    # Compute uri and filters
    if subsidiary:
        scope_current_filter = "subsidiary_id=%s" % subsidiary.id
        scope_current_url_filter = "subsidiary/%s" % subsidiary.id
    elif team:
        scope_current_filter = "team_id=%s" % team.id
        scope_current_url_filter = "team/%s" % team.id
    else:
        scope_current_filter = ""
        scope_current_url_filter = ""

    return scopes, scope_current_filter, scope_current_url_filter


def compute_consultant_tasks(consultant):
    """gather all tasks consultant should do
    @:return: list of (task_name, count, link, priority(1-3))"""
    tasks = []
    now = datetime.now()
    user = consultant.get_user()

    if not user:
        return tasks

    # Expenses to reviews
    expenses = Expense.objects.filter(user__in=user_expense_team(user), workflow_in_progress=True, state="REQUESTED")
    expenses_count = expenses.count()
    if expenses_count > 0:
        expenses_age = (now - expenses.aggregate(Min("update_date"))["update_date__min"]).days
        expenses_priority = get_task_priority(expenses_age, (5, 10))
        tasks.append((_("Expenses to review"), expenses_count, reverse("expense:expenses")+"#managed_expense_workflow_table", expenses_priority))

    # Client bills to reviews
    bills = ClientBill.objects.filter(state="0_DRAFT", billdetail__mission__responsible=consultant).distinct()
    bills_count = bills.count()
    if bills_count > 0:
        bills_age = (now.date() - bills.aggregate(Min("creation_date"))["creation_date__min"]).days
        bills_priority = get_task_priority(bills_age, (2, 5))
        tasks.append((_("Bills to review"), bills_count, reverse("billing:client_bills_in_creation"), bills_priority ))

    # Supplier bills to reviews
    supplier_bills = SupplierBill.objects.filter(state="1_RECEIVED", lead__responsible=consultant)
    supplier_bills_count = supplier_bills.count()
    if supplier_bills_count > 0:
        supplier_bills_age = (now.date() - supplier_bills.aggregate(Min("creation_date"))["creation_date__min"]).days
        supplier_bills_priority = get_task_priority(supplier_bills_age, (2, 5))
        tasks.append((_("Supplier bills to review"), supplier_bills_count, reverse("billing:bill_review")+"#supplier_soondue_bills", supplier_bills_priority))

    # Actions
    actions = consultant.pending_actions()
    actions_count = actions.count()
    if actions_count:
        actions_priority = get_task_priority(actions_count, (10, 20))
        tasks.append((_("Pending actions"), actions_count, "#consultant_actions", actions_priority))

    return tasks


def get_task_priority(value, threshold):
    """determine task priority according threshold (medium/high)"""
    if value > threshold[1]:
        return 3
    elif value > threshold[0]:
        return 2
    else:
        return 1
