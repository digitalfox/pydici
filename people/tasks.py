# coding: utf-8

"""
Module that handle asynchronous tasks
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import datetime, date
import random
from dataclasses import dataclass

from django.db.models import Min, Count, Q, F, Sum, Max
from django.urls import reverse
from django.utils.translation import gettext as _
from django.core.cache import cache
from django.apps import apps

from celery import shared_task

from core.utils import nextMonth


@dataclass
@dataclass
class ConsultantTask:
    """Group of tasks to be done by consultants"""
    label: str
    count: int
    link: str
    priority: int
    category: str


@shared_task
def compute_consultant_tasks(consultant_id):
    """compute consultants tasks and cache results
    Tasks computed:
    - expenses that require reviews (workflow action)
    - missions without defined billing mode
    - missions with missing financial conditions
    - client bills in draft mode
    - supplier bills to be validated
    - leads without tag
    - leads with past due date

    :return: list of tasks. Task is a tuple like ("label", count, link, priority)
    """
    # Use get_model to avoid circular imports
    Expense = apps.get_model("expense", "Expense")
    Mission = apps.get_model("staffing", "Mission")
    SupplierBill = apps.get_model("billing", "SupplierBill")
    ClientBill = apps.get_model("billing", "ClientBill")
    Consultant = apps.get_model("people", "Consultant")
    Lead = apps.get_model("leads", "Lead")
    Staffing = apps.get_model("staffing", "Staffing")
    ClientOrganisation = apps.get_model("crm", "ClientOrganisation")
    from people.models import CONSULTANT_TASKS_CACHE_KEY

    consultant = Consultant.objects.get(id=consultant_id)

    tasks = []
    now = datetime.now()
    current_month = date.today().replace(day=1)
    user = consultant.get_user()

    if not user:
        return []

    # Expenses to reviews as manager
    expenses = Expense.objects.filter(user__in=consultant.user_team(exclude_self=False), workflow_in_progress=True, state="REQUESTED")
    expenses_count = expenses.count()
    if expenses_count > 0:
        expenses_link = reverse("expense:expenses") + "#managed_expense_workflow_table"
        expenses_age = (now - expenses.aggregate(Min("update_date"))["update_date__min"]).days
        expenses_priority = get_task_priority(expenses_age, (7, 14))
        tasks.append(ConsultantTask(label=_("Expenses to review"), category=_("expenses"), count=expenses_count,
                                    priority=expenses_priority, link=expenses_link))

    # Self expenses waiting for information
    expenses = Expense.objects.filter(user=user, workflow_in_progress=True, state="NEEDS_INFORMATION")
    expenses_count = expenses.count()
    if expenses_count > 0:
        expenses_link = reverse("expense:expenses")
        expenses_age = (now - expenses.aggregate(Min("update_date"))["update_date__min"]).days
        expenses_priority = get_task_priority(expenses_age, (7, 14))
        tasks.append(ConsultantTask(label=_("Expenses needs information"), category=_("expenses"), count=expenses_count,
                                    priority=expenses_priority, link=expenses_link))

    # Missions without billing mode
    missions_without_billing_mode = Mission.objects.filter(responsible=consultant, active=True,
                                                           nature="PROD", billing_mode=None)
    missions_without_billing_mode_count = missions_without_billing_mode.count()
    if missions_without_billing_mode_count > 0:
        tasks.append(ConsultantTask(label=_("Mission without billing mode"), category=_("missions"), count=missions_without_billing_mode_count,
                                    link=reverse("staffing:mission_home", args=[random.choice(missions_without_billing_mode).id]), priority=3))

    # Missions with missing financial conditions
    missions_with_missing_fc = [ m for m in Mission.objects.filter(active=True, nature="PROD", responsible=consultant) if not m.defined_rates()]
    missions_with_missing_fc_count = len(missions_with_missing_fc)
    if missions_with_missing_fc_count > 0:
        tasks.append(ConsultantTask(label=_("Consultants rates are not fully defined"), count=missions_with_missing_fc_count,
                                    category=_("missions"), priority=3,
                                    link=reverse("staffing:mission_home", args=[random.choice(missions_with_missing_fc).id])))

    # Mission with missing marketing product
    missions_with_missing_mktg_pdt = Mission.objects.filter(active=True, nature="PROD", responsible=consultant, marketing_product__isnull=True)
    missions_with_missing_mktg_pdt_count = missions_with_missing_mktg_pdt.count()
    if missions_with_missing_mktg_pdt_count > 0:
        tasks.append(ConsultantTask(label=_("Mission marketing product is missing"), count=missions_with_missing_mktg_pdt_count,
                                    category=_("missions"), priority=1,
                                    link=reverse("staffing:mission_home", args=[random.choice(missions_with_missing_mktg_pdt).id])))

    # Done work without billing
    still_to_be_billed = 0
    still_to_be_billed_count = 0
    still_to_be_billed_leads = []
    for lead in Lead.objects.filter(responsible=consultant, mission__active=True).distinct():
        amount = lead.still_to_be_billed(include_fixed_price=False, include_current_month=False)
        if amount > 0:
            still_to_be_billed += int(amount)
            still_to_be_billed_count += 1
            still_to_be_billed_leads.append(lead)
    if still_to_be_billed_count > 0:
        tasks.append(ConsultantTask(label=_("%s € missing billing for past months") % still_to_be_billed, count=still_to_be_billed_count,
                                    priority=3, category=_("billing"),
                                    link=reverse("billing:client_billing_control_pivotable") + "?responsible=" + str(consultant.id)))

    # Client bills to reviews
    bills = ClientBill.objects.filter(state="0_DRAFT", billdetail__mission__responsible=consultant).distinct()
    bills_count = bills.count()
    if bills_count > 0:
        bills_age = (now.date() - bills.aggregate(Min("creation_date"))["creation_date__min"]).days
        bills_priority = get_task_priority(bills_age, (5, 10))
        tasks.append(ConsultantTask(label=_("Bills to review"), count=bills_count, category=_("billing"),
                                    link=reverse("billing:client_bills_in_creation"), priority=bills_priority))

    # Supplier bills to reviews
    supplier_bills = SupplierBill.objects.filter(state="1_RECEIVED", lead__responsible=consultant)
    supplier_bills_count = supplier_bills.count()
    if supplier_bills_count > 0:
        supplier_bills_age = (now.date() - supplier_bills.aggregate(Min("creation_date"))["creation_date__min"]).days
        supplier_bills_priority = get_task_priority(supplier_bills_age, (4, 7))
        tasks.append(ConsultantTask(label=_("Supplier bills to review"), count=supplier_bills_count, category=_("billing"),
                                    link=reverse("billing:supplier_bills_validation"), priority=supplier_bills_priority))

    # leads without tag
    leads_without_tag = consultant.active_leads().annotate(Count("tags")).filter(tags__count=0)
    leads_without_tag_count = leads_without_tag.count()
    if leads_without_tag_count > 0:
        tasks.append(ConsultantTask(label=_("Leads without tag"), count=leads_without_tag_count, priority=1,
                                    category=_("leads"), link=reverse("leads:detail", args=[random.choice(leads_without_tag).id])))

    # leads with past due date
    leads_with_past_due_date = consultant.active_leads().filter(due_date__lt=date.today())
    leads_with_past_due_date_count = leads_with_past_due_date.count()
    if leads_with_past_due_date_count > 0:
        tasks.append(ConsultantTask(label=_("Leads with past due date"), count=leads_with_past_due_date_count, category=_("leads"),
                                    priority=1, link=reverse("leads:detail", args=[random.choice(leads_with_past_due_date).id])))

    # active client organisation with incomplete legal information
    incomplete_client_orga = ClientOrganisation.objects.filter(client__active=True, company__businessOwner=consultant)
    incomplete_client_orga = incomplete_client_orga.filter(Q(legal_id__isnull=True) | Q(vat_id__isnull=True)).distinct()
    incomplete_client_orga_count = incomplete_client_orga.count()
    if incomplete_client_orga_count > 0:
        tasks.append(ConsultantTask(label=_("Missing legal id or vat id"), count=incomplete_client_orga_count,
                                    category=_("billing"), priority=1,
                                    link=reverse("crm:client_organisation_change", args=[random.choice(incomplete_client_orga).id]),))

    # timesheet way beyond forecasted staffing
    # Note: we use Max to aggregate staffing because join on timesheet multiple lines.
    overshoot_missions = Mission.objects.filter(active=True, staffing__consultant=consultant, staffing__staffing_date=current_month)\
        .annotate(forecasted=Max("staffing__charge", filter=Q(staffing__staffing_date=current_month, staffing__consultant=consultant)))\
        .annotate(done=Sum("timesheet__charge", filter=Q(timesheet__working_date__gte=current_month,
            timesheet__working_date__lt=nextMonth(current_month), timesheet__consultant=consultant)))\
        .filter(done__gt=F("forecasted"))

    overshoot_missions_count = overshoot_missions.count()
    if overshoot_missions_count > 0:
        overshoot_missions_priority = get_task_priority(overshoot_missions_count, (2, 5))
        tasks.append(ConsultantTask(label=_("Timesheet beyond forecasted staffing this month"), count=overshoot_missions_count,
                                    category=_("timesheet"), priority=overshoot_missions_priority,
                                    link=reverse("people:consultant_home_by_id", args=[consultant.id])+"#tab-timesheet"))

    # update cache with computed tasks
    cache.set(CONSULTANT_TASKS_CACHE_KEY % consultant.id, tasks, 24*3600)


@shared_task
def compute_all_consultants_tasks():
    """Compute all active consultant tasks and cache results"""
    Consultant = apps.get_model("people", "Consultant")
    for consultant in Consultant.objects.filter(active=True, subcontractor=False):
        compute_consultant_tasks(consultant.id)


def get_task_priority(value, threshold):
    """determine task priority according threshold (medium/high)"""
    if value > threshold[1]:
        return 3
    elif value > threshold[0]:
        return 2
    else:
        return 1
