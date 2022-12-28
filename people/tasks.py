# coding: utf-8

"""
Module that handle asynchronous tasks
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import datetime

from django.db.models import Min
from django.urls import reverse
from django.utils.translation import gettext as _
from django.core.cache import cache
from django.apps import apps

from celery import shared_task

from people.models import CONSULTANT_TASKS_CACHE_KEY


@shared_task
def compute_consultant_tasks(consultant_id):
    """compute consultants tasks and cache results
    Tasks computed:
    - expenses that require reviews (workflow action)
    - missions without defined billing mode
    - client bills in draft mode
    - supplier bills to be validated
    """
    # Use get_model to avoid circular imports
    Expense = apps.get_model("expense", "Expense")
    Mission = apps.get_model("staffing", "Mission")
    SupplierBill = apps.get_model("billing", "SupplierBill")
    ClientBill = apps.get_model("billing", "ClientBill")
    Consultant = apps.get_model("people", "Consultant")

    consultant = Consultant.objects.get(id=consultant_id)

    tasks = []
    now = datetime.now()
    user = consultant.get_user()

    if not user:
        return []

    # Expenses to reviews
    expenses = Expense.objects.filter(user__in=consultant.user_team(exclude_self=False), workflow_in_progress=True, state="REQUESTED")
    expenses_count = expenses.count()
    if expenses_count > 0:
        expenses_age = (now - expenses.aggregate(Min("update_date"))["update_date__min"]).days
        expenses_priority = get_task_priority(expenses_age, (5, 10))
        tasks.append((_("Expenses to review"), expenses_count, reverse("expense:expenses")+"#managed_expense_workflow_table", expenses_priority))

    # Missions without billing mode
    missions_without_billing_mode = Mission.objects.filter(responsible=consultant, active=True,
                                                           nature="PROD", billing_mode=None)
    missions_without_billing_mode_count = missions_without_billing_mode.count()
    if missions_without_billing_mode_count > 0:
        tasks.append((_("Mission without billing mode"), missions_without_billing_mode_count,
                      reverse("staffing:mission_home", args=[missions_without_billing_mode[0].id]), 3))

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

    # update cache with computed tasks
    cache.set(CONSULTANT_TASKS_CACHE_KEY % consultant.id, tasks, 24*3600)
    return tasks

@shared_task
def compute_all_consultants_tasks():
    """Compute all active consultant tasks and cache results"""
    Consultant = apps.get_model("people", "Consultant")
    for consultant in Consultant.objects(active=True, subcontractor=False):
        compute_consultant_tasks(consultant.id)

def get_task_priority(value, threshold):
    """determine task priority according threshold (medium/high)"""
    if value > threshold[1]:
        return 3
    elif value > threshold[0]:
        return 2
    else:
        return 1
