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
from billing.models import ClientBill
from expense.models import Expense
from expense.utils import user_expense_team

def getScopes(subsidiary, team, target="all"):
    """Define scopes than can be used to filter data. Either team, subsidiary or everybody (default). Format is (type, filter, label) where type is "team_id" or "subsidiary_id".
    @:param target: all (default), subsidiary or team
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
    user = consultant.getUser()

    # Expenses to reviews
    expenses = Expense.objects.filter(user__in=user_expense_team(user), workflow_in_progress=True, state="REQUESTED")
    expenses_count = expenses.count()
    if expenses_count > 0:
        expenses_age = (now - expenses.aggregate(Min("update_date"))["update_date__min"]).days
        if expenses_age > 10:
            expenses_priority = 3
        elif expenses_age > 5:
            expenses_priority = 2
        else:
            expenses_priority = 1
        tasks.append((_("Expenses to review"), expenses_count, reverse("expense:expenses")+"#managed_expense_workflow_table", expenses_priority))

    # Client bills to reviews
    bills = ClientBill.objects.filter(state="0_DRAFT", billdetail__mission__responsible=consultant).distinct()
    bills_count = bills.count()
    if bills_count > 0:
        tasks.append((_("Bills to review"), bills_count, reverse("billing:client_bills_in_creation"), 1))

    # Supplier bills to reviews
    # TODO

    # Actions
    actions = consultant.pending_actions()
    actions_count = actions.count()
    if actions_count > 20:
        actions_priority = 3
    elif actions_count > 10:
        actions_priority = 2
    else:
        actions_priority = 1
    if actions_count:
        tasks.append((_("Pending actions"), actions_count, "#consultant_actions", actions_priority))

    return tasks

