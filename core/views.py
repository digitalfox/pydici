# coding: utf-8
"""
Pydici core views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import csv
import datetime

from django.shortcuts import render
from django.db.models import Q, Sum
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import numberformat
from django.utils.html import strip_tags

from core.decorator import pydici_non_public
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
    try:
        consultant = Consultant.objects.get(trigramme__iexact=request.user.username)
    except Consultant.DoesNotExist:
        consultant = None

    if consultant:
        return consultant_home(request, consultant.id)
    else:
        # User is not a consultant. Go for default index page.
        return render(request, "core/pydici.html",
                      {"user": request.user})


@pydici_non_public
def search(request):
    """Very simple search function on all major pydici objects"""

    words = request.GET.get("q", "")
    words = words.split()
    consultants = companies = contacts = leads = missions = bills = None

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
        contacts = contacts.distinct()

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
        leads = leads.distinct()

        # Missions
        missions = Mission.objects.all()
        for word in words:
            missions = missions.filter(Q(deal_id__icontains=word) |
                                       Q(description__icontains=word))

        # Add missions from lead
        if leads:
            missions = set(missions)
            for lead in leads:
                for mission in lead.mission_set.all():
                    missions.add(mission)
            missions = list(missions)

        # Bills
        bills = ClientBill.objects.all()
        for word in words:
            bills = bills.filter(Q(bill_id__icontains=word) |
                                 Q(comment__icontains=word))

        # Add bills from lead
        if leads:
            bills = set(bills)
            for lead in leads:
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
                   "missions": missions,
                   "bills": bills,
                   "user": request.user})


@pydici_non_public
def dashboard(request):
    """Tactical management dashboard. This views is in core module because it aggregates data
    accross different modules"""

    return render(request, "core/dashboard.html")


@pydici_non_public
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
              "ObjectiveRate", "DailyRate", "BoughtDailyRate", "BudgetType", "QuantityInDays", "QuantityInEuros"]

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
            missionRow.append(numberformat.format(mission.lead.sales, ",") if mission.lead.sales else 0)
            if mission.lead.responsible:
                missionRow.append(mission.lead.responsible.name)
                missionRow.append(mission.lead.responsible.trigramme)
                missionRow.append(mission.lead.responsible.manager.trigramme if mission.lead.responsible.manager else "")
            else:
                missionRow.extend(["", "", ""])
        else:
            missionRow.extend(["", "", "", "", "", 0, "", "", ""])
        missionRow.append(mission.description or "")
        missionRow.append(mission.mission_id())
        missionRow.append(mission.billing_mode or "")
        missionRow.append(numberformat.format(mission.price, ",") if mission.price else 0)
        missionRow.extend(mission.done_work())
        return missionRow

    for mission in missions:
        missionRow = createMissionRow(mission, start_date, end_date)
        for consultant in mission.consultants().select_related().prefetch_related("manager"):
            consultantRow = missionRow[:]  # copy
            daily_rate, bought_daily_rate = financialConditions.get("%s-%s" % (mission.id, consultant.id), [0, 0])
            rateObjective = consultant.getRateObjective(end_date)
            if rateObjective:
                rateObjective = rateObjective.daily_rate
            else:
                rateObjective = 0
            doneDays = timesheets.filter(mission_id=mission.id, consultant=consultant.id).aggregate(Sum("charge")).values()[0] or 0
            forecastedDays = staffings.filter(mission_id=mission.id, consultant=consultant.id).aggregate(Sum("charge")).values()[0] or 0
            consultantRow.append(consultant.company)
            consultantRow.append(consultant.manager.trigramme if consultant.manager else "")
            consultantRow.append(consultant.trigramme)
            consultantRow.append(consultant.name)
            consultantRow.append(consultant.subcontractor)
            consultantRow.append(mission.subsidiary != consultant.company)
            consultantRow.append(numberformat.format(rateObjective, ","))
            consultantRow.append(numberformat.format(daily_rate, ",") if daily_rate else 0)
            consultantRow.append(numberformat.format(bought_daily_rate, ",") if bought_daily_rate else 0)
            # Timesheet row
            for budgetType, quantity in (("done", doneDays), ("forecast", forecastedDays)):
                row = consultantRow[:]  # Copy
                row.append(budgetType)
                row.append(numberformat.format(quantity, ",") if quantity else 0)
                row.append(numberformat.format(quantity * daily_rate, ",") if (quantity > 0 and daily_rate > 0) else 0)
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
            row.append(consultant.manager.trigramme)
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


def tableToCSV(table, filename="data.csv"):
    """A view that convert a django_table2 object to a CSV in a http response object"""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s" % filename
    writer = csv.writer(response, delimiter=';')
    header = [column.header for column in table.columns]
    writer.writerow([h.encode("iso8859-1") for h in header])
    for row in table.rows:
        row = [strip_tags(cell) for column, cell in row.items()]
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
