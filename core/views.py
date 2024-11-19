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
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from django.utils.translation import pgettext
from django.core.cache import cache
from django.conf import settings
from django.apps import apps

from django_select2.views import AutoResponseView
from taggit.models import Tag

from core.decorator import pydici_non_public, pydici_feature, PydiciNonPublicdMixin, PydiciSubcontractordMixin
from leads.models import Lead
from people.models import Consultant
from crm.models import Company, Contact
from crm.utils import get_subsidiary_from_session
from staffing.models import Mission, FinancialCondition, Staffing, Timesheet
from billing.models import ClientBill
from expense.models import Expense
from people.views import consultant_home
from core.utils import nextMonth, previousMonth, get_fiscal_year, user_has_feature



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
    words = words.split()[:10]  # limits search to 10 words
    words = [w for w in words if len(w) > 1]  # remove one letter words
    consultants = companies = contacts = leads = active_missions = archived_missions = bills = tags = None
    max_record = 50
    more_record = False  # Whether we have more records
    subsidiary = get_subsidiary_from_session(request)

    if len(words) == 1:
        word = words[0]
        # Try to find perfect match
        try:
            lead = Lead.objects.get(deal_id=word)
            return HttpResponseRedirect(lead.get_absolute_url())
        except Lead.DoesNotExist:
            pass
        try:
            consultant = Consultant.objects.get(trigramme=word)
            return HttpResponseRedirect(consultant.get_absolute_url())
        except Consultant.DoesNotExist:
            pass

    if words:
        # Consultant
        consultants = Consultant.objects.all()
        for word in words:
            consultants = consultants.filter(Q(name__icontains=word) |
                                             Q(trigramme__icontains=word))
        consultants = consultants.distinct().order_by("-active", "name", )
        if subsidiary:
            consultants = consultants.filter(company=subsidiary)

        # Companies
        companies = Company.objects.all()
        for word in words:
            companies = companies.filter(Q(name__icontains=word) |
                                         Q(code__iexact=word))
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
        leads = leads.distinct()
        if subsidiary:
            leads = leads.filter(subsidiary=subsidiary)
        leads = leads.select_related("client__organisation__company")[:max_record]
        if len(leads) >= max_record:
            more_record = True

        # Missions
        missions = Mission.objects.all()
        for word in words:
            missions = missions.filter(Q(deal_id__icontains=word) |
                                       Q(description__icontains=word))
        if subsidiary:
            missions = missions.filter(subsidiary=subsidiary)
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

        archived_missions = []
        active_missions = []
        for mission in missions:
            if mission.active:
                active_missions.append(mission)
            else:
                archived_missions.append(mission)

        # Bills
        bills = ClientBill.objects.all()
        for word in words:
            bills = bills.filter(Q(bill_id__icontains=word) |
                                 Q(comment__icontains=word))
        if subsidiary:
            bills = bills.filter(lead__subsidiary=subsidiary)
        bills = bills.select_related("lead__client__organisation__company")[:max_record]
        if len(bills) >= max_record:
            more_record = True

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
                   "active_missions": active_missions,
                   "archived_missions": archived_missions,
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
def financial_control(request, start_date=None, end_date=None):
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
              "Subsidiary", "ClientCompany", "ClientCompanyCode", "ClientOrganization",
              "Lead", "DealId", "LeadPrice", "Billed", "LeadResponsible", "LeadResponsibleTrigramme", "LeadTeam",
              "Mission", "MissionId", "AnalyticCode", "AnalyticDescription", "BillingMode", "MissionPrice",
              "TotalQuantityInDays", "TotalQuantityInEuros", "LastTimesheet",
              "ConsultantSubsidiary", "ConsultantTeam", "Trigramme", "Consultant", "Subcontractor", "CrossBilling",
              "ObjectiveRate", "DailyRate", "BoughtDailyRate", "BudgetType", "QuantityInDays", "QuantityInEuros",
              "StartDate", "EndDate"]

    writer.writerow(header)

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
        missionRow.append(get_fiscal_year(start_date))
        missionRow.append(end_date.isoformat())
        missionRow.append("timesheet")
        missionRow.append(mission.nature)
        missionRow.append(not mission.active)
        if mission.lead:
            missionRow.append(mission.lead.subsidiary)
            missionRow.append(mission.lead.client.organisation.company.name)
            missionRow.append(mission.lead.client.organisation.company.code)
            missionRow.append(mission.lead.client.organisation.name)
            missionRow.append(mission.lead.name)
            missionRow.append(mission.lead.deal_id)
            missionRow.append(mission.lead.sales or 0)
            missionRow.append(list(mission.lead.clientbill_set.filter(state__in=("1_SENT", "2_PAID"), creation_date__lt=end_date, creation_date__gte=start_date).aggregate(Sum("amount")).values())[0] or 0)
            if mission.lead.responsible:
                missionRow.append(mission.lead.responsible.name)
                missionRow.append(mission.lead.responsible.trigramme)
                missionRow.append(mission.lead.responsible.staffing_manager.trigramme if mission.lead.responsible.staffing_manager else "")
            else:
                missionRow.extend(["", "", ""])
        else:
            missionRow.extend([mission.subsidiary, "", "", "", "", "", 0, 0, "", "", ""])
        missionRow.append(mission.description or "")
        missionRow.append(mission.mission_id())
        missionRow.append(mission.mission_analytic_code())
        missionRow.append(mission.analytic_code.description if mission.analytic_code else "")
        missionRow.append(mission.billing_mode or "")
        missionRow.append(mission.price or 0)
        missionRow.extend(mission.done_work_period(None, nextMonth(end_date)))
        last_timesheet = Timesheet.objects.filter(mission=mission).aggregate(Max("working_date"))["working_date__max"]
        missionRow.append(last_timesheet.isoformat() if last_timesheet else "")
        return missionRow

    for mission in missions:
        missionRow = createMissionRow(mission, start_date, end_date)
        for consultant in mission.consultants().select_related().prefetch_related("staffing_manager"):
            consultantRow = missionRow[:]  # copy
            daily_rate, bought_daily_rate = financialConditions.get("%s-%s" % (mission.id, consultant.id), [0, 0])
            rateObjective = consultant.get_rate_objective(working_date=end_date, rate_type="DAILY_RATE")
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
            if mission.lead:
                consultantRow.append(mission.lead.subsidiary != consultant.company)
            else:
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
                writer.writerow(row)

    archivedMissions = Mission.objects.filter(active=False, archived_date__gte=start_date, archived_date__lt=end_date)
    archivedMissions = archivedMissions.filter(lead__state="WON")
    archivedMissions = archivedMissions.prefetch_related("lead__client__organisation__company", "lead__responsible")
    for mission in archivedMissions:
        if mission in missions:
            # Mission has already been processed for this period
            continue
        missionRow = createMissionRow(mission, start_date, end_date)
        writer.writerow(missionRow)

    for expense in Expense.objects.filter(expense_date__gte=start_date, expense_date__lt=nextMonth(end_date), chargeable=False).select_related():
        row = []
        row.append(get_fiscal_year(start_date))
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
        writer.writerow(row)

    return response


@pydici_non_public
@pydici_feature("reports")
def risk_reporting(request):
    """Risk reporting synthesis"""
    data = []
    today = datetime.date.today()
    subsidiary = get_subsidiary_from_session(request)
    # Sent bills (still not paid)
    bills = ClientBill.objects.filter(state="1_SENT")
    if subsidiary:
        bills = bills.filter(lead__subsidiary=subsidiary)
    for bill in bills.select_related():
        if bill.due_date < today:
            data_type = _("overdue bills")
        else:
            data_type = _("sent bills")
        data.append({_("type"): data_type,
                     _("subsidiary"): str(bill.lead.subsidiary),
                     _("deal_id"): bill.lead.deal_id,
                     _("deal"): bill.lead.name,
                     _("amount"): int(bill.amount),
                     _("company"): str(bill.lead.client.organisation.company),
                     _("client"): str(bill.lead.client),
                     })

    # Leads with done works beyond sent or paid bills
    leads = Lead.objects.filter(mission__active=True)
    if subsidiary:
        leads = leads.filter(subsidiary=subsidiary)
    for lead in leads.distinct().select_related():
        if not "TIME_SPENT" in [m.billing_mode for m in lead.mission_set.all()]:
            # All missions of this lead are fixed price (no one is time spent). So done works beyond billing is not considered here
            # Fixed price mission tracking is done a separate report
            continue
        done_d, done_a = lead.done_work()
        billed = float(ClientBill.objects.filter(lead=lead).filter(Q(state="1_SENT") | Q(state="2_PAID")).aggregate(amount=Sum("amount"))["amount"] or 0)
        if billed < done_a:
            data.append({_("type"): _("work without bill"),
                         _("subsidiary"): str(lead.subsidiary),
                         _("deal_id"): lead.deal_id,
                         _("deal"): lead.name,
                         _("amount"): int(done_a - billed),
                         _("company"): str(lead.client.organisation.company),
                         _("client"): str(lead.client),
                         })

    return render(request, "core/risks.html", { "data": json.dumps(data),
                                                    "derivedAttributes": []})


class PydiciSelect2View(PydiciNonPublicdMixin, AutoResponseView):
    """Overload default select2 view that is used to get data through ajax calls to limit it to internal users"""
    pass

class PydiciSelect2SubcontractorView(PydiciSubcontractordMixin, AutoResponseView):
    """Select2 endpoint Overload default select2 view that is used to get data through ajax calls to limit it to internal users and subcontractor"""
    pass


def tableToCSV(table, filename="data.csv"):
    """A view that convert a django_table2 object to a CSV in a http response object"""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s" % filename
    writer = csv.writer(response, delimiter=';')
    header = [column.header for column in table.columns]
    writer.writerow(header)
    for row in table.rows:
        row = [strip_tags(str(cell)) for column, cell in list(row.items())]
        row = [i.replace("\u2714", _("Yes")).replace("\u2718", _("No")) for i in row]
        writer.writerow(row)
    return response


def forbidden(request):
    """When access is denied..."""
    if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest' or request.META.get("HTTP_HX_REQUEST"):
        # Ajax request, use stripped forbidden page
        template = "core/_access_forbidden.html"
    else:
        # Standard request, use complete forbidden page with menu
        template = "core/forbidden.html"
    if settings.DEBUG:
        status = 200  # Needed to trigger userswitch middleware
    else:
        status = 403  # Regular forbidden return code
    return render(request, template,
                  {"admins": settings.ADMINS, },
                  status=status)


def object_history(request, object_type, object_id):
    """Fragment page that display given object history"""
    # placeholder for log translation
    pgettext("noun", "add")
    pgettext("noun", "delete")
    # Key is object type and value (Model class, required feature name)
    history_models = {"lead": [apps.get_model("leads", "Lead"), "leads"],
                      "mission": [apps.get_model("staffing", "Mission"), "staffing"],
                      "clientbill": [apps.get_model("billing", "ClientBill"), "billing_request"],
                      "supplierbill": [apps.get_model("billing", "SupplierBill"), "billing_request"],
                      "expense": [apps.get_model("expense", "Expense"), "expense"]
                      }

    model, feature = history_models[object_type]
    if not user_has_feature(request.user, feature):
        return forbidden(request)

    try:
        o = model.objects.get(id=object_id)
    except model.DoesNotExist:
        raise Http404
    return render(request, "core/_object_history.html", {"object": o})
