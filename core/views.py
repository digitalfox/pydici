# coding: utf-8
"""
Pydici core views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import csv
import datetime
import json

from django.shortcuts import render
from django.db.models import Q, Sum, Min, Max
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.html import strip_tags
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.core.cache import cache

from django_select2.views import AutoResponseView
from taggit.models import Tag

from core.decorator import pydici_non_public, pydici_feature, PydiciNonPublicdMixin
from leads.models import Lead
from people.models import Consultant
from crm.models import Company, Contact
from staffing.models import Mission, FinancialCondition, Staffing, Timesheet
from billing.models import ClientBill
from expense.models import Expense
from people.views import consultant_home
from core.utils import nextMonth, previousMonth

import pydici.settings


@login_required
def index(request):
    key = "core.index." + request.user.username
    consultant_trigramme = cache.get(key)
    if consultant_trigramme is None:
        try:
            consultant_trigramme = Consultant.objects.get(trigramme__iexact=request.user.username).trigramme
            cache.set(key, consultant_trigramme)
        except Consultant.DoesNotExist:
            consultant_trigramme = None

    if consultant_trigramme:
        return consultant_home(request, consultant_trigramme)
    else:
        # User is not a consultant. Go for default index page.
        return render(request, "core/pydici.html",
                      {"user": request.user})


@pydici_non_public
@pydici_feature("search")
def search(request):
    """Very simple search function on all major pydici objects"""

    words = request.GET.get("q", "")
    words = words.split()
    consultants = companies = contacts = leads = missions = bills = tags = None
    max_record = 50
    more_record = False # Wether we have more records

    if words:
        # Consultant
        consultants = Consultant.objects.filter(active=True)
        for word in words:
            consultants = consultants.filter(Q(name__icontains=word) |
                                             Q(trigramme__icontains=word))
        consultants = consultants.distinct()

        # Companies
        companies = Company.objects.all()
        for word in words:
            companies = companies.filter(name__icontains=word)
        companies = companies.distinct()

        # Contacts
        contacts = Contact.objects.all()
        for word in words:
            contacts = contacts.filter(name__icontains=word)
        contacts = contacts.distinct()[:max_record]
        if len(contacts) >= max_record:
            more_record = True

        # Tags
        tags = Tag.objects.all()
        for word in words:
            tags = tags.filter(name__icontains=word)

        # Leads
        leads = Lead.objects.all()
        for word in words:
            leads = leads.filter(Q(name__icontains=word) |
                                 Q(description__icontains=word) |
                                 Q(tags__name__iexact=word) |
                                 Q(client__contact__name__icontains=word) |
                                 Q(client__organisation__company__name__icontains=word) |
                                 Q(client__organisation__name__iexact=word) |
                                 Q(deal_id__icontains=word[:-1]))  # Squash last letter that could be mission letter
        leads = leads.distinct().select_related("client__organisation__company")[:max_record]
        if len(leads) >= max_record:
            more_record = True

        # Missions
        missions = Mission.objects.all()
        for word in words:
            missions = missions.filter(Q(deal_id__icontains=word) |
                                       Q(description__icontains=word))
        missions = missions.select_related("lead__client__organisation__company")[:max_record]
        if len(missions) >= max_record:
            more_record = True

        # Add missions from lead
        if leads:
            missions = set(missions)
            for lead in leads.prefetch_related("mission_set"):
                for mission in lead.mission_set.all():
                    missions.add(mission)
            missions = list(missions)

        # Bills
        bills = ClientBill.objects.all()
        for word in words:
            bills = bills.filter(Q(bill_id__icontains=word) |
                                 Q(comment__icontains=word))
        bills = bills.select_related("lead__client__organisation__company")[:max_record]
        if len(bills) >= max_record:
            more_record = True

        # Add bills from lead
        if leads:
            bills = set(bills)
            for lead in leads.prefetch_related("clientbill_set"):
                for bill in lead.clientbill_set.all():
                    bills.add(bill)
        # Sort
        bills = list(bills)
        bills.sort(key=lambda x: x.creation_date)

    return render(request, "core/search.html",
                  {"query": " ".join(words),
                   "consultants": consultants,
                   "companies": companies,
                   "contacts": contacts,
                   "leads": leads,
                   "tags": tags,
                   "missions": missions,
                   "bills": bills,
                   "more_record": more_record,
                   "user": request.user})


@pydici_non_public
@pydici_feature("reports")
def dashboard(request):
    """Tactical management dashboard. This views is in core module because it aggregates data
    accross different modules"""

    return render(request, "core/dashboard.html")


@pydici_non_public
@pydici_feature("reports")
def financialControl(request, start_date=None, end_date=None):
    """Financial control extraction. This view is intented to be processed by
    a spreadsheet or a financial package software"""
    if end_date is None:
        end_date = previousMonth(datetime.date.today())
    else:
        end_date = datetime.date(int(end_date[0:4]), int(end_date[4:6]), 1)
    if start_date is None:
        start_date = previousMonth(previousMonth(datetime.date.today()))
    else:
        start_date = datetime.date(int(start_date[0:4]), int(start_date[4:6]), 1)

    response = HttpResponse(content_type="text/plain")
    response["Content-Disposition"] = "attachment; filename=financialControl.dat"
    writer = csv.writer(response, delimiter=';')

    financialConditions = {}
    for fc in FinancialCondition.objects.all():
        financialConditions["%s-%s" % (fc.mission_id, fc.consultant_id)] = (fc.daily_rate, fc.bought_daily_rate)

    # Header
    header = ["FiscalYear", "Month", "Type", "Nature", "Archived",
              "MissionSubsidiary", "ClientCompany", "ClientCompanyCode", "ClientOrganization",
              "Lead", "DealId", "LeadPrice", "LeadResponsible", "LeadResponsibleTrigramme", "LeadTeam",
              "Mission", "MissionId", "BillingMode", "MissionPrice",
              "TotalQuantityInDays", "TotalQuantityInEuros",
              "ConsultantSubsidiary", "ConsultantTeam", "Trigramme", "Consultant", "Subcontractor", "CrossBilling",
              "ObjectiveRate", "DailyRate", "BoughtDailyRate", "BudgetType", "QuantityInDays", "QuantityInEuros",
              "StartDate", "EndDate"]

    writer.writerow([unicode(i).encode("ISO-8859-15", "ignore") for i in header])

    timesheets = Timesheet.objects.filter(working_date__gte=start_date, working_date__lt=nextMonth(end_date))
    staffings = Staffing.objects.filter(staffing_date__gte=start_date, staffing_date__lt=nextMonth(end_date))

    consultants = dict([(i.trigramme.lower(), i) for i in Consultant.objects.all().select_related()])

    missionsIdsFromStaffing = Mission.objects.filter(probability__gt=0, staffing__staffing_date__gte=start_date, staffing__staffing_date__lt=nextMonth(end_date)).values_list("id", flat=True)
    missionsIdsFromTimesheet = Mission.objects.filter(probability__gt=0, timesheet__working_date__gte=start_date, timesheet__working_date__lt=nextMonth(end_date)).values_list("id", flat=True)
    missionsIds = set(list(missionsIdsFromStaffing) + list(missionsIdsFromTimesheet))
    missions = Mission.objects.filter(id__in=missionsIds)
    missions = missions.distinct().select_related().prefetch_related("lead__client__organisation__company", "lead__responsible")

    def createMissionRow(mission, start_date, end_date):
        """Inner function to create mission row"""
        missionRow = []
        missionRow.append(start_date.year)
        missionRow.append(end_date.isoformat())
        missionRow.append("timesheet")
        missionRow.append(mission.nature)
        missionRow.append(not mission.active)
        missionRow.append(mission.subsidiary)
        if mission.lead:
            missionRow.append(mission.lead.client.organisation.company.name)
            missionRow.append(mission.lead.client.organisation.company.code)
            missionRow.append(mission.lead.client.organisation.name)
            missionRow.append(mission.lead.name)
            missionRow.append(mission.lead.deal_id)
            missionRow.append(mission.lead.sales or 0)
            if mission.lead.responsible:
                missionRow.append(mission.lead.responsible.name)
                missionRow.append(mission.lead.responsible.trigramme)
                missionRow.append(mission.lead.responsible.staffing_manager.trigramme if mission.lead.responsible.staffing_manager else "")
            else:
                missionRow.extend(["", "", ""])
        else:
            missionRow.extend(["", "", "", "", "", 0, "", "", ""])
        missionRow.append(mission.description or "")
        missionRow.append(mission.mission_id())
        missionRow.append(mission.billing_mode or "")
        missionRow.append(mission.price or 0)
        missionRow.extend(mission.done_work())
        return missionRow

    for mission in missions:
        missionRow = createMissionRow(mission, start_date, end_date)
        for consultant in mission.consultants().select_related().prefetch_related("staffing_manager"):
            consultantRow = missionRow[:]  # copy
            daily_rate, bought_daily_rate = financialConditions.get("%s-%s" % (mission.id, consultant.id), [0, 0])
            rateObjective = consultant.getRateObjective(end_date, rate_type="DAILY_RATE")
            if rateObjective:
                rateObjective = rateObjective.rate
            else:
                rateObjective = 0
            doneDays = timesheets.filter(mission_id=mission.id, consultant=consultant.id).aggregate(charge=Sum("charge"), min_date=Min("working_date"), max_date=Max("working_date"))
            forecastedDays = staffings.filter(mission_id=mission.id, consultant=consultant.id).aggregate(charge=Sum("charge"), min_date=Min("staffing_date"), max_date=Max("staffing_date"))
            consultantRow.append(consultant.company)
            consultantRow.append(consultant.staffing_manager.trigramme if consultant.staffing_manager else "")
            consultantRow.append(consultant.trigramme)
            consultantRow.append(consultant.name)
            consultantRow.append(consultant.subcontractor)
            consultantRow.append(mission.subsidiary != consultant.company)
            consultantRow.append(rateObjective)
            consultantRow.append(daily_rate or 0)
            consultantRow.append(bought_daily_rate or 0)
            # Timesheet row
            for budgetType, days in (("done", doneDays), ("forecast", forecastedDays)):
                quantity = days["charge"] or 0
                row = consultantRow[:]  # Copy
                row.append(budgetType)
                row.append(quantity or 0)
                row.append((quantity * daily_rate) if (quantity > 0 and daily_rate > 0) else 0)
                row.append(days["min_date"] or "")
                row.append(days["max_date"] or "")
                writer.writerow([unicode(i).encode("ISO-8859-15", "ignore") for i in row])

    archivedMissions = Mission.objects.filter(active=False, archived_date__gte=start_date, archived_date__lt=end_date)
    archivedMissions = archivedMissions.filter(lead__state="WON")
    archivedMissions = archivedMissions.prefetch_related("lead__client__organisation__company", "lead__responsible")
    for mission in archivedMissions:
        if mission in missions:
            # Mission has already been processed for this period
            continue
        missionRow = createMissionRow(mission, start_date, end_date)
        writer.writerow([unicode(i).encode("ISO-8859-15", "ignore") for i in missionRow])

    for expense in Expense.objects.filter(expense_date__gte=start_date, expense_date__lt=nextMonth(end_date), chargeable=False).select_related():
        row = []
        row.append(start_date.year)
        row.append(end_date.isoformat())
        row.append("expense")
        row.append(expense.category)
        if expense.lead:
            row.append(expense.lead.subsidiary)
            row.extend(["", "", "", ""])
            row.append(expense.lead.deal_id)
        else:
            row.extend(["", "", "", "", "", ""])
        row.extend(["", "", "", "", ""])
        try:
            consultant = consultants[expense.user.username.lower()]
            row.append(consultant.company.name)
            row.append(consultant.staffing_manager.trigramme)
            row.append(consultant.trigramme)
            row.append(consultant.name)
            row.append(consultant.subcontractor)
            if expense.lead:
                row.append(expense.lead.subsidiary != consultant.company)
            else:
                row.append("unknown for now")
        except KeyError:
            # Exepense user is not a consultant
            row.extend(["", "", "", "", "", ""])
        row.extend(["", "", "", "", ""])
        row.append(expense.amount)  # TODO: compute pseudo HT amount
        writer.writerow([unicode(i).encode("ISO-8859-15", "ignore") for i in row])

    return response


@pydici_non_public
@pydici_feature("reports")
def riskReporting(request):
    """Risk reporting synthesis"""
    data = []
    today = datetime.date.today()
    # Sent bills (still not paid)
    for bill in ClientBill.objects.filter(state="1_SENT").select_related():
        if bill.due_date < today:
            data_type = _("overdue bills")
        else:
            data_type = _("sent bills")
        data.append({_("type"): data_type,
                     _("subsidiary"): unicode(bill.lead.subsidiary),
                     _("deal_id"): bill.lead.deal_id,
                     _("deal"): bill.lead.name,
                     _("amount"): int(bill.amount),
                     _("company"): unicode(bill.lead.client.organisation.company),
                     _("client"): unicode(bill.lead.client),
                     })

    # Leads with done works beyond sent or paid bills
    for lead in Lead.objects.filter(state="WON", mission__active=True).distinct().select_related():
        if not "TIME_SPENT" in [m.billing_mode for m in lead.mission_set.all()]:
            # All missions of this lead are fixed price (no one is time spent). So done works beyond billing is not considered here
            # Fixed price mission tracking is done a separate report
            continue
        done_d, done_a = lead.done_work()
        billed = float(ClientBill.objects.filter(lead=lead).filter(Q(state="1_SENT") | Q(state="2_PAID")).aggregate(amount=Sum("amount"))["amount"] or 0)
        if billed < done_a:
            data.append({_("type"): _("work without bill"),
                         _("subsidiary"): unicode(lead.subsidiary),
                         _("deal_id"): lead.deal_id,
                         _("deal"): lead.name,
                         _("amount"): int(done_a - billed),
                         _("company"): unicode(lead.client.organisation.company),
                         _("client"): unicode(lead.client),
                         })

    return render(request, "core/risks.html", { "data": json.dumps(data),
                                                    "derivedAttributes": []})


class PydiciSelect2View(PydiciNonPublicdMixin, AutoResponseView):
    """Overload default select2 view that is used to get data through ajax calls to limit it to login users"""
    pass


def tableToCSV(table, filename="data.csv"):
    """A view that convert a django_table2 object to a CSV in a http response object"""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s" % filename
    writer = csv.writer(response, delimiter=';')
    header = [column.header for column in table.columns]
    writer.writerow([h.encode("iso8859-1") for h in header])
    for row in table.rows:
        row = [strip_tags(unicode(cell)) for column, cell in row.items()]
        row = [i.replace(u"\u2714", _("No")).replace(u"\u2718", _("Yes")) for i in row]
        writer.writerow([item.encode("iso8859-1", "ignore") for item in row])
    return response


def internal_error(request):
    """Custom internal error view.
    Like the default builtin one, but with context to allow proper menu display with correct media path"""
    return render(request, "500.html")


def forbiden(request):
    """When access is denied..."""
    if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        # Ajax request, use stripped forbiden page
        template = "core/_access_forbiden.html"
    else:
        # Standard request, use full forbiden page with menu
        template = "core/forbiden.html"
    return render(request, template,
                  {"admins": pydici.settings.ADMINS, })
