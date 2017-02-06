# coding: utf-8
"""
Pydici staffing views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta, datetime
import csv
import json

from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.contrib.auth.decorators import permission_required
from django.forms.models import inlineformset_factory
from django.utils.translation import ugettext as _
from django.core import urlresolvers
from django.db.models import Sum, Count, Q
from django.db import connections
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.utils import formats
from django.views.decorators.cache import cache_page, cache_control
from django.views.generic.edit import UpdateView
from django.contrib import messages
from django.conf import settings
from django.template.loader import get_template

from staffing.models import Staffing, Mission, Holiday, Timesheet, FinancialCondition, LunchTicket
from people.models import Consultant, Subsidiary
from leads.models import Lead
from people.models import ConsultantProfile
from staffing.forms import ConsultantStaffingInlineFormset, MissionStaffingInlineFormset, \
    TimesheetForm, MassStaffingForm, MissionContactsForm
from core.utils import working_days, nextMonth, previousMonth, daysOfMonth, previousWeek, nextWeek, monthWeekNumber, \
    to_int_or_round, COLORS, convertDictKeyToDate, cumulateList, user_has_feature
from core.decorator import pydici_non_public, pydici_feature, PydiciNonPublicdMixin
from staffing.utils import gatherTimesheetData, saveTimesheetData, saveFormsetAndLog, \
    sortMissions, holidayDays, staffingDates, time_string_for_day_percent
from staffing.forms import MissionForm
from people.utils import getScopes

TIMESTRING_FORMATTER = {
    'cycle': formats.number_format,
    'keyboard': time_string_for_day_percent
}


TIMESHEET_ACCESS_NOT_ALLOWED = 'N'
TIMESHEET_ACCESS_READ_ONLY = 'RO'
TIMESHEET_ACCESS_READ_WRITE = 'RW'


def check_user_timesheet_access(user, consultant, timesheet_month):
    """
    Check if the user is allowed to access the requested timesheet.
    Returns one of the `TIMESHEET_ACCESS_*` constants.
    """
    current_month = date.today().replace(day=1)

    if (user.has_perm("staffing.add_timesheet") and
            user.has_perm("staffing.change_timesheet") and
            user.has_perm("staffing.delete_timesheet")):
        return TIMESHEET_ACCESS_READ_WRITE

    try:
        trigramme = user.username.upper()
        user_consultant = Consultant.objects.get(trigramme=trigramme)
    except Consultant.DoesNotExist:
        return TIMESHEET_ACCESS_NOT_ALLOWED

    if user_consultant.id == consultant.id:
        # User is accessing his own timesheet

        # A consultant can only edit his own timesheet on current month and 3 days after
        timesheet_next_month = (timesheet_month + timedelta(days=40)).replace(day=1)
        if current_month == timesheet_month or (date.today() - timesheet_next_month).days <= 3:
            return TIMESHEET_ACCESS_READ_WRITE
        else:
            return TIMESHEET_ACCESS_READ_ONLY

    # User is accessing the timesheet of another user
    if user_consultant.subcontractor:
        return TIMESHEET_ACCESS_NOT_ALLOWED

    if user_has_feature(user, "timesheet_all"):
        return TIMESHEET_ACCESS_READ_ONLY

    if user_has_feature(user, "timesheet_current_month"):
        if timesheet_month >= current_month:
            return TIMESHEET_ACCESS_READ_ONLY
        else:
            return TIMESHEET_ACCESS_NOT_ALLOWED
    else:
        return TIMESHEET_ACCESS_NOT_ALLOWED


@pydici_non_public
def missions(request, onlyActive=True):
    """List of missions"""
    if onlyActive:
        data_url = urlresolvers.reverse('active_mission_table_DT')
    else:
        data_url = urlresolvers.reverse('all_mission_table_DT')
    return render(request, "staffing/missions.html",
                  {"all": not onlyActive,
                   "data_url": data_url,
                   "datatable_options": ''' "columnDefs": [{ "orderable": false, "targets": [4, 6, 7, 8] },
                                                             { className: "hidden-xs hidden-sm hidden-md", "targets": [6,7]}],
                                             "order": [[0, "asc"]] ''',
                   "user": request.user})


@pydici_non_public
def mission_home(request, mission_id):
    """Home page of mission description - this page loads all others mission sub-pages"""
    mission = Mission.objects.get(id=mission_id)
    return render(request, 'staffing/mission.html',
                  {"mission": mission,
                   "user": request.user})


@pydici_non_public
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def mission_staffing(request, mission_id):
    """Edit mission staffing"""
    if (request.user.has_perm("staffing.add_staffing") and
        request.user.has_perm("staffing.change_staffing") and
        request.user.has_perm("staffing.delete_staffing")):
        readOnly = False
    else:
        readOnly = True

    if not request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        # This view should only be accessed by ajax request. Redirect lost users
        return redirect(mission_home, mission_id)

    StaffingFormSet = inlineformset_factory(Mission, Staffing,
                                            formset=MissionStaffingInlineFormset,
                                            fields="__all__")
    mission = Mission.objects.get(id=mission_id)
    if request.method == "POST":
        if readOnly:
            # Readonly users should never go here !
            return HttpResponseRedirect(urlresolvers.reverse("forbiden"))
        formset = StaffingFormSet(request.POST, instance=mission)
        if formset.is_valid():
            saveFormsetAndLog(formset, request)
            formset = StaffingFormSet(instance=mission)  # Recreate a new form for next update
    else:
        formset = StaffingFormSet(instance=mission)  # An unbound form

    return render(request, 'staffing/mission_staffing.html',
                  {"formset": formset,
                   "mission": mission,
                   "read_only": readOnly,
                   "staffing_dates": staffingDates(),
                   "user": request.user})


@pydici_non_public
@pydici_feature("staffing")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def consultant_staffing(request, consultant_id):
    """Edit consultant staffing"""
    consultant = Consultant.objects.get(id=consultant_id)

    if not (request.user.has_perm("staffing.add_staffing") and
            request.user.has_perm("staffing.change_staffing") and
            request.user.has_perm("staffing.delete_staffing")):
        # Only forbid access if the user try to edit someone else staffing
        if request.user.username.upper() != consultant.trigramme:
            return HttpResponseRedirect(urlresolvers.reverse("forbiden"))

    StaffingFormSet = inlineformset_factory(Consultant, Staffing,
                                          formset=ConsultantStaffingInlineFormset, fields="__all__")

    if request.method == "POST":
        formset = StaffingFormSet(request.POST, instance=consultant)
        if formset.is_valid():
            saveFormsetAndLog(formset, request)
            formset = StaffingFormSet(instance=consultant)  # Recreate a new form for next update
    else:
        formset = StaffingFormSet(instance=consultant)  # An unbound form

    return render(request, 'staffing/consultant_staffing.html',
                  {"formset": formset,
                   "consultant": consultant,
                   "staffing_dates": staffingDates(),
                   "user": request.user})


@pydici_non_public
@pydici_feature("staffing_mass")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def mass_staffing(request):
    """Massive staffing form"""
    staffing_dates = [(i, formats.date_format(i, format="YEAR_MONTH_FORMAT")) for i in staffingDates(format="datetime")]
    now = datetime.now().replace(microsecond=0)  # Remove useless microsecond that pollute form validation in callback
    if request.method == 'POST':  # If the form has been submitted...
        form = MassStaffingForm(request.POST, staffing_dates=staffing_dates)
        if form.is_valid():  # All validation rules pass
            # Process the data in form.cleaned_data
            if form.cleaned_data["all_consultants"]:
                # Get all active, productive non subcontractors consultants
                consultants = Consultant.objects.filter(active=True, productive=True, subcontractor=False)
            else:
                # Use selected consultants
                consultants = form.cleaned_data["consultants"]
            for mission in form.cleaned_data["missions"]:
                for consultant in consultants:
                    for staffing_date in form.cleaned_data["staffing_dates"]:
                        staffing_date = date(*[int(i) for i in staffing_date.split("-")])
                        staffing, created = Staffing.objects.get_or_create(consultant=consultant,
                                                                           mission=mission,
                                                                           staffing_date=staffing_date,
                                                                           defaults={"consultant": consultant,
                                                                                     "mission": mission,
                                                                                     "staffing_date": staffing_date})
                        staffing.charge = form.cleaned_data["charge"]
                        staffing.comment = form.cleaned_data["comment"]
                        staffing.update_date = now
                        staffing.last_user = unicode(request.user)
                        staffing.save()
            # Redirect to self to display a new unbound form
            messages.add_message(request, messages.INFO, _("Staffing has been updated"))
            return HttpResponseRedirect(urlresolvers.reverse("staffing.views.mass_staffing"))
    else:
        # An unbound form
        form = MassStaffingForm(staffing_dates=staffing_dates)

    return render(request, "staffing/mass_staffing.html",
                  {"form": form,
                   "staffing_dates": staffing_dates})


@pydici_non_public
@pydici_feature("staffing_mass")
def pdc_review(request, year=None, month=None):
    """PDC overview
    @param year: start date year. None means current year
    @param year: start date year. None means current month,
    Request option parameters:
    - team: only display this team (staffing manager id)
    - subsidiary: only display this subsidiary (subsidiary id)
    - n_month: number of month to display in forceast
    - projection: projection mode (nonce, balanced, full) used to filter still-not-won leads"""

    team = None
    subsidiary = None

    # Various projections modes. Value is ("short name", "description")
    projections = {"none": (_(u"Only won leads"), _(u"Only consider won leads for staffing forecasting")),
                   "balanced": (_(u"Balanced staffing projection"), _(u"Add missions forcecast staffing even if still not won with a ponderation based on the mission won probability")),
                   "full": (_(u"Full staffing projection"), _(u"Add missions forcecast staffing even if still not won without any ponderation. All forecast is considered."))}

    # Group by modes. Value is label
    groups = {"manager": _(u"Group by Manager"),
              "level": _(u"Group by Level")}

    # Get team and subsidiary
    if "team_id" in request.GET:
        team = Consultant.objects.get(id=int(request.GET["team_id"]))
    if "subsidiary_id" in request.GET:
        subsidiary = Subsidiary.objects.get(id=int(request.GET["subsidiary_id"]))

    # Don't display this page if no productive consultant are defined
    people = Consultant.objects.filter(productive=True).filter(active=True).filter(subcontractor=False)
    if team:
        people = people.filter(staffing_manager=team)
    if subsidiary:
        people = people.filter(staffing_manager__company=subsidiary)
    people_count = people.count()
    if people_count == 0:
        # TODO: make this message nice
        return HttpResponse(_("No productive consultant defined !"))

    n_month = 3  # Default number of month to display

    if "n_month" in request.GET:
        try:
            n_month = int(request.GET["n_month"])
            if n_month > 12:
                n_month = 12  # Limit to 12 month to avoid complex and useless month list computation
        except ValueError:
            pass

    projection = "balanced"
    if "projection" in request.GET:
        if request.GET["projection"] in ("none", "balanced", "full"):
            projection = request.GET["projection"]

    groupby = "manager"
    if "groupby" in request.GET:
        if request.GET["groupby"] in ("manager", "level"):
            groupby = request.GET["groupby"]

    if year and month:
        start_date = date(int(year), int(month), 1)
    else:
        start_date = date.today()
        start_date = start_date.replace(day=1)  # We use the first day to represent month

    staffing = {}  # staffing data per month and per consultant
    total = {}  # total staffing data per month
    rates = []  # staffing rates per month
    available_month = {}  # available working days per month
    months = []  # list of month to be displayed

    #TODO: simplify this !! Use nextMonth
    for i in range(n_month):
        if start_date.month + i <= 12:
            months.append(start_date.replace(month=start_date.month + i))
        else:
            # We wrap around a year (max one year)
            months.append(start_date.replace(month=start_date.month + i - 12, year=start_date.year + 1))

    previous_slice_date = start_date - timedelta(days=(28 * n_month))
    next_slice_date = start_date + timedelta(days=(31 * n_month))

    # Initialize total dict and available dict
    holidays_days = Holiday.objects.all().values_list("day", flat=True)
    for month in months:
        total[month] = {"prod": 0, "unprod": 0, "holidays": 0, "available": 0, "total": 0}
        available_month[month] = working_days(month, holidays_days)

    # Get consultants staffing
    consultants = Consultant.objects.filter(productive=True).filter(active=True).filter(subcontractor=False).select_related("staffing_manager")
    if team:
        consultants = consultants.filter(staffing_manager=team)
    if subsidiary :
        consultants = consultants.filter(company=subsidiary)
    for consultant in consultants:
        staffing[consultant] = []
        missions = set()
        for month in months:
            if projection in ("balanced", "full"):
                # Only exclude null (0%) mission
                current_staffings = consultant.staffing_set.filter(staffing_date=month, mission__probability__gt=0).order_by()
            else:
                # Only keep 100% mission
                current_staffings = consultant.staffing_set.filter(staffing_date=month, mission__probability=100).order_by()

            # Sum staffing
            prod = []
            unprod = []
            holidays = []
            for current_staffing  in current_staffings.select_related("mission__lead__client__organisation__company"):
                nature = current_staffing.mission.nature
                if nature == "PROD":
                    missions.add(current_staffing.mission)  # Store prod missions for this consultant
                    if projection == "full":
                        prod.append(current_staffing.charge)
                    else:
                        prod.append(current_staffing.charge * current_staffing.mission.probability / 100)
                elif nature == "NONPROD":
                    if projection == "full":
                        unprod.append(current_staffing.charge)
                    else:
                        unprod.append(current_staffing.charge * current_staffing.mission.probability / 100)
                elif nature == "HOLIDAYS":
                    if projection == "full":
                        holidays.append(current_staffing.charge)
                    else:
                        holidays.append(current_staffing.charge * current_staffing.mission.probability / 100)

            # Staffing computation
            prod = sum(prod)
            unprod = sum(unprod)
            holidays = sum(holidays)
            prod_round = to_int_or_round(prod)
            unprod_round = to_int_or_round(unprod)
            holidays_round = to_int_or_round(holidays)
            available = available_month[month] - (prod + unprod + holidays)
            available_displayed = available_month[month] - (prod_round + unprod_round + holidays_round)
            staffing[consultant].append([prod_round, unprod_round, holidays_round, available_displayed])
            total[month]["prod"] += prod
            total[month]["unprod"] += unprod
            total[month]["holidays"] += holidays
            total[month]["available"] += available
            total[month]["total"] += available_month[month]
        # Add client synthesis to staffing dict
        company = set([m.lead.client.organisation.company for m in list(missions) if m.lead is not None])
        client_list = ", ".join(["<a href='%s'>%s</a>" %
                                (urlresolvers.reverse("crm.views.company_detail", args=[c.id]), unicode(c)) for c in company])
        client_list = "<div class='hidden-xs hidden-sm'>%s</div>" % client_list
        staffing[consultant].append([client_list])

    # Compute indicator rates
    for month in months:
        rate = []
        ndays = people_count * available_month[month]  # Total days for this month
        for indicator in ("prod", "unprod", "holidays", "available"):
            if indicator == "holidays":
                rate.append(100.0 * total[month][indicator] / ndays)
            else:
                rate.append(100.0 * total[month][indicator] / (ndays - total[month]["holidays"]))
        rates.append(map(to_int_or_round, rate))

    # Format total dict into list
    total = total.items()
    total.sort(cmp=lambda x, y: cmp(x[0], y[0]))  # Sort according date
    # Remove date, and transform dict into ordered list:
    total = [(to_int_or_round(i[1]["prod"]),
            to_int_or_round(i[1]["unprod"]),
            to_int_or_round(i[1]["holidays"]),
            i[1]["total"] - (to_int_or_round(i[1]["prod"]) + to_int_or_round(i[1]["unprod"]) + to_int_or_round(i[1]["holidays"]))) for i in total]

    # Order staffing list
    staffing = staffing.items()
    staffing.sort(cmp=lambda x, y: cmp(x[0].name, y[0].name))  # Sort by name
    if groupby == "manager":
        staffing.sort(cmp=lambda x, y: cmp(unicode(x[0].staffing_manager), unicode(y[0].staffing_manager)))  # Sort by staffing manager
    else:
        staffing.sort(cmp=lambda x, y: cmp(x[0].profil.level, y[0].profil.level))  # Sort by level

    scopes, scope_current_filter, scope_current_url_filter = getScopes(subsidiary, team)
    if team:
        team_name = _(u"team %(manager_name)s") % {"manager_name": team}
    else:
        team_name = None

    return render(request, "staffing/pdc_review.html",
                  {"staffing": staffing,
                   "months": months,
                   "total": total,
                   "rates": rates,
                   "user": request.user,
                   "projection": projection,
                   "projection_label" : projections[projection][0],
                   "projections": projections,
                   "previous_slice_date": previous_slice_date,
                   "next_slice_date": next_slice_date,
                   "start_date": start_date,
                   "groupby": groupby,
                   "groupby_label": groups[groupby],
                   "groups": groups,
                   "scope": subsidiary or team_name or _(u"Everybody"),
                   "scope_current_filter" : scope_current_filter,
                   "scope_current_url_filter": scope_current_url_filter,
                   "scopes": scopes,})


@pydici_non_public
@pydici_feature("staffing_mass")
@cache_page(10)
def pdc_detail(request, consultant_id, staffing_date):
    """Display detail of consultant staffing for this month"""
    try:
        consultant = Consultant.objects.get(id=consultant_id)
    except Consultant.DoesNotExist:
        raise Http404
    try:
        month = date(int(staffing_date[0:4]), int(staffing_date[4:6]), 1)
    except (ValueError, IndexError):
        raise Http404

    staffings = Staffing.objects.filter(mission__active=True, consultant=consultant, staffing_date__gte=month, staffing_date__lt=nextMonth(month))
    return render(request, "staffing/pdc_detail.html",
                  {"staffings": staffings,
                   "user": request.user})


@pydici_non_public
@pydici_feature("reports")
def prod_report(request, year=None, month=None):
    """Report production by each people and team for each month"""
    #TODO: extract that in CSV as well

    team = None
    subsidiary = None
    months = []
    n_month = 5
    tooltip_template = get_template("staffing/_consultant_prod_tooltip.html")

    all_status = {"ok": "#43E707",
                  "ko": "#E76F6F",
                  "ok_but_daily_rate": "#CCE7B2",
                  "ok_but_prod_date": "#A2E774",
                  "ko_but_daily_rate": "#E7E36D",
                  "ko_but_prod_date": "#F99E9E"}

    # Get time frame
    if year and month:
        end_date = date(int(year), int(month), 1)
        if end_date > date.today():
            end_date = date.today().replace(day=1)
    else:
        end_date = date.today().replace(day=1)

    start_date = (end_date - timedelta(30 * n_month)).replace(day=1)

    current_date = start_date
    while current_date < end_date:
        current_date = nextMonth(current_date)
        months.append(current_date)

    previous_slice_date = end_date - timedelta(days=(28 * n_month))
    next_slice_date = end_date + timedelta(days=(31 * n_month))

    # Get team and subsidiary
    if "team_id" in request.GET:
        team = Consultant.objects.get(id=int(request.GET["team_id"]))
    if "subsidiary_id" in request.GET:
        subsidiary = Subsidiary.objects.get(id=int(request.GET["subsidiary_id"]))

    # Filter on scope
    consultants = Consultant.objects.filter(productive=True).filter(active=True).filter(
        subcontractor=False).select_related("staffing_manager")
    if team:
        consultants = consultants.filter(staffing_manager=team)
    if subsidiary:
        consultants = consultants.filter(company=subsidiary)

    holidays_days = Holiday.objects.filter(day__gte=start_date, day__lte=end_date).values_list("day", flat=True)
    data = []
    totalDone = {}
    totalForecasted = {}

    for consultant in consultants:
        consultantData = []
        for month in months:
            if month not in totalDone:
                totalDone[month] = 0
            if month not in totalForecasted:
                totalForecasted[month] = 0
            upperBound = min(date.today(), nextMonth(month))
            month_days = working_days(month, holidays=holidays_days, upToToday=True)
            timesheets = Timesheet.objects.filter(consultant=consultant,
                                                  charge__gt=0,
                                                  working_date__gte=month,
                                                  working_date__lt=upperBound)
            consultant_days = dict(timesheets.values_list("mission__nature").order_by("mission__nature").annotate(Sum("charge")))

            try:
                daily_rate_obj = consultant.getRateObjective(workingDate=month, rate_type="DAILY_RATE").rate
                prod_rate_obj = float(consultant.getRateObjective(workingDate=month, rate_type="PROD_RATE").rate) / 100
                forecast = int(daily_rate_obj * prod_rate_obj * (month_days - consultant_days.get("HOLIDAYS",0)))
            except AttributeError:
                prod_rate_obj = daily_rate_obj = forecast = 0 # At least one rate objective is missing
            turnover = int(consultant.getTurnover(month, upperBound))
            try:
                prod_rate = consultant_days.get("PROD", 0) / (consultant_days.get("PROD", 0) + consultant_days.get("NONPROD", 0))
            except ZeroDivisionError:
                prod_rate = 0
            if consultant_days.get("PROD", 0) > 0:
                daily_rate = turnover / consultant_days["PROD"]
            else:
                daily_rate = 0
            if turnover >= forecast:
                if prod_rate < prod_rate_obj:
                    status = all_status["ok_but_prod_date"]
                elif daily_rate < daily_rate_obj:
                    status = all_status["ok_but_daily_rate"]
                else:
                    status = all_status["ok"]
            else:
                if prod_rate >= prod_rate_obj:
                    status = all_status["ko_but_prod_date"]
                elif daily_rate >= daily_rate_obj:
                    status = all_status["ko_but_daily_rate"]
                else:
                    status = all_status["ko"]
            tooltip = tooltip_template.render({"daily_rate": daily_rate, "daily_rate_obj": daily_rate_obj, "prod_rate": prod_rate * 100, "prod_rate_obj": prod_rate_obj * 100})
            consultantData.append([status, tooltip, [formats.number_format(turnover), formats.number_format(forecast)]]) # For each month : [status, [turnover, forceast ]]
            totalDone[month] += turnover
            totalForecasted[month] += forecast
        data.append([consultant, consultantData])

    # Add total
    totalData = []
    for month in months:
        forecast = totalForecasted[month]
        turnover = totalDone[month]
        if forecast > turnover:
            status = all_status["ko"]
        else:
            status = all_status["ok"]
        totalData.append([status, "", [formats.number_format(turnover), formats.number_format(forecast)]])
    data.append([None, None, totalData])

    # Get scopes
    scopes, scope_current_filter, scope_current_url_filter = getScopes(subsidiary, team)
    if team:
        team_name = _(u"team %(manager_name)s") % {"manager_name": team}
    else:
        team_name = None

    return render(request, "staffing/prod_report.html",
                  {"data": data,
                   "months": months,
                   "end_date" : end_date,
                   "previous_slice_date": previous_slice_date,
                   "next_slice_date": next_slice_date,
                   "scope": subsidiary or team_name or _(u"Everybody"),
                   "scope_current_filter": scope_current_filter,
                   "scope_current_url_filter": scope_current_url_filter,
                   "scopes": scopes })

@pydici_non_public
@pydici_feature("reports")
def fixed_price_missions_report(request):
    """Report current fixed price mission margin"""
    data = []

    missions = Mission.objects.filter(active=True, nature="PROD", billing_mode="FIXED_PRICE")

    # Get team and subsidiary
    if "subsidiary_id" in request.GET:
        subsidiary = Subsidiary.objects.get(id=int(request.GET["subsidiary_id"]))
        missions = missions.filter(subsidiary=subsidiary)
    else:
        subsidiary = None

    for mission in missions.select_related():
        #TODO: we mess up with objective margin that is computed for current but not target margin. Same issue in mission_tiemsheet page
        current_margin = round(mission.margin() + sum(mission.objectiveMargin().values()) / 1000, 1)
        target_margin = round(mission.margin(mode="target"), 1)
        data.append((mission, round(mission.done_work_k()[1],1), current_margin, target_margin))

    # Get scopes
    scopes, scope_current_filter, scope_current_url_filter = getScopes(subsidiary, None, target="subsidiary")

    return render(request, "staffing/fixed_price_report.html",
                  {"data": data,
                   "scope": subsidiary or _(u"Everybody"),
                   "scope_current_filter": scope_current_filter,
                   "scope_current_url_filter": scope_current_url_filter,
                   "scopes": scopes })


@pydici_non_public
def deactivate_mission(request, mission_id):
    """Deactivate the given mission"""
    try:
        error = False
        mission = Mission.objects.get(id=mission_id)
        mission.active = False
        mission.save()
    except Mission.DoesNotExist:
        error = True
    return HttpResponse(json.dumps({"error": error, "id": mission_id}),
                        content_type="application/json")


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def consultant_timesheet(request, consultant_id, year=None, month=None, week=None):
    """Consultant timesheet"""

    # We use the first day to represent month
    if year and month:
        month = date(int(year), int(month), 1)
    else:
        month = date.today().replace(day=1)

    if week:
        week = int(week)

    if date.today().replace(day=1) == month:
        today = datetime.today().day
    else:
        today = 0

    forecastTotal = {}  # forecast charge (value) per mission (key is mission.id)
    missions = set()  # Set of all consultant missions for this month
    days = daysOfMonth(month, week=week)  # List of days in month

    if week:
        previous_date = previousWeek(days[0])
        next_date = nextWeek(days[0])
        previous_week = monthWeekNumber(previous_date)
        next_week = monthWeekNumber(next_date)
    else:
        previous_date = (month - timedelta(days=5)).replace(day=1)
        next_date = (month + timedelta(days=40)).replace(day=1)
        previous_week = 0
        next_week = 0

    notAllowed = HttpResponseRedirect(urlresolvers.reverse("forbiden"))

    consultant = Consultant.objects.get(id=consultant_id)

    access = check_user_timesheet_access(request.user, consultant, month)

    if access == TIMESHEET_ACCESS_NOT_ALLOWED:
        return notAllowed
    readOnly = access == TIMESHEET_ACCESS_READ_ONLY

    staffings = Staffing.objects.filter(consultant=consultant)
    staffings = staffings.filter(staffing_date=month)
    for staffing in staffings.select_related("mission"):
        if staffing.mission.id in forecastTotal:
            forecastTotal[staffing.mission.id] += staffing.charge
        else:
            forecastTotal[staffing.mission.id] = staffing.charge

    # Missions with already defined timesheet or forecasted for this month
    missions = set(list(consultant.forecasted_missions(month=month)) + list(consultant.timesheet_missions(month=month)))
    missions = sortMissions(missions)

    # Add zero forecast for mission with active timesheet but no more forecast
    for mission in missions:
        if not mission.id in forecastTotal:
            forecastTotal[mission.id] = 0

    if "csv" in request.GET:
        return consultant_csv_timesheet(request, consultant, days, month, missions)

    timesheetData, timesheetTotal, warning = gatherTimesheetData(consultant, missions, month)

    holiday_days = holidayDays(month=month)

    if request.method == 'POST':  # If the form has been submitted...
        if readOnly:
            # We should never go here as validate button is not displayed when read only...
            # This is just a security control
            return HttpResponseRedirect(urlresolvers.reverse("forbiden"))
        form = TimesheetForm(request.POST, days=days, missions=missions, holiday_days=holiday_days, showLunchTickets=not consultant.subcontractor,
                             forecastTotal=forecastTotal, timesheetTotal=timesheetTotal)
        if form.is_valid():  # All validation rules pass
            # Process the data in form.cleaned_data
            saveTimesheetData(consultant, month, form.cleaned_data, timesheetData)
            # Recreate a new form for next update and compute again totals
            timesheetData, timesheetTotal, warning = gatherTimesheetData(consultant, missions, month)
            form = TimesheetForm(days=days, missions=missions, holiday_days=holiday_days, showLunchTickets=not consultant.subcontractor,
                                 forecastTotal=forecastTotal, timesheetTotal=timesheetTotal, initial=timesheetData)
    else:
        # An unbound form
        form = TimesheetForm(days=days, missions=missions, holiday_days=holiday_days, showLunchTickets=not consultant.subcontractor,
                             forecastTotal=forecastTotal, timesheetTotal=timesheetTotal, initial=timesheetData)

    # Compute workings days of this month and compare it to declared days
    wDays = working_days(month, holiday_days)
    wDaysBalance = wDays - (sum(timesheetTotal.values()) - timesheetTotal["ticket"])

    # Shrink warning list to given week if week number is given
    if week:
        warning = warning[days[0].day - 1:days[-1].day]

    previous_date_enabled = check_user_timesheet_access(request.user, consultant, previous_date.replace(day=1)) != TIMESHEET_ACCESS_NOT_ALLOWED

    return render(request, "staffing/consultant_timesheet.html",
                  {"consultant": consultant,
                   "form": form,
                   "read_only": readOnly,
                   "days": days,
                   "month": month,
                   "week": week or 0,
                   "missions": missions,
                   "working_days_balance": wDaysBalance,
                   "working_days": wDays,
                   "warning": warning,
                   "next_date": next_date,
                   "previous_date": previous_date,
                   "previous_date_enabled": previous_date_enabled,
                   "previous_week": previous_week,
                   "next_week": next_week,
                   "today": today,
                   "is_current_month": month == date.today().replace(day=1),
                   "user": request.user})

def consultant_csv_timesheet(request, consultant, days, month, missions):
    """@return: csv timesheet for a given consultant"""
    # This "view" is never called directly but only through consultant_timesheet view
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s" % _("timesheet.csv")
    writer = csv.writer(response, delimiter=';')

    # Header
    writer.writerow([("%s - %s" % (unicode(consultant), month)).encode("ISO-8859-15", "replace"), ])

    # Days
    writer.writerow(["", ""] + [d.day for d in days])
    writer.writerow([_("Mission").encode("ISO-8859-15", "replace"), _("Deal id").encode("ISO-8859-15", "replace")]
                     + [_(d.strftime("%a")) for d in days] + [_("total")])

    timestring_formatter = TIMESTRING_FORMATTER[settings.TIMESHEET_INPUT_METHOD]

    for mission in missions:
        total = 0
        row = [i.encode("ISO-8859-15", "replace") for i in [unicode(mission), mission.mission_id()]]
        timesheets = Timesheet.objects.select_related().filter(consultant=consultant).filter(mission=mission)
        for day in days:
            try:
                timesheet = timesheets.get(working_date=day)
                row.append(timestring_formatter(timesheet.charge))
                total += timesheet.charge
            except Timesheet.DoesNotExist:
                row.append("")
        row.append(formats.number_format(total))
        writer.writerow(row)

    return response


@pydici_non_public
def mission_timesheet(request, mission_id):
    """Mission timesheet"""
    dateTrunc = connections[Timesheet.objects.db].ops.date_trunc_sql  # Shortcut to SQL date trunc function
    mission = Mission.objects.get(id=mission_id)
    current_month = date.today().replace(day=1)  # Current month
    consultants = mission.consultants()
    consultant_rates = mission.consultant_rates()

    if "csv" in request.GET:
        return mission_csv_timesheet(request, mission, consultants)

    if not request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        # This view should only be accessed by ajax request. Redirect lost users
        return redirect(mission_home, mission_id)

    # Gather timesheet (Only consider timesheet up to current month)
    timesheets = Timesheet.objects.filter(mission=mission).filter(working_date__lt=nextMonth(current_month)).order_by("working_date")
    timesheetMonths = list(timesheets.dates("working_date", "month"))

    # Gather forecaster (till current month)
    staffings = Staffing.objects.filter(mission=mission).filter(staffing_date__gte=current_month).order_by("staffing_date")
    staffingMonths = list(staffings.dates("staffing_date", "month"))

    missionData = []  # list of tuple (consultant, (charge month 1, charge month 2), (forecast month 1, forcast month2), estimated)
    for consultant in consultants:
        # Timesheet data
        timesheetData = []
        data = dict(timesheets.filter(consultant=consultant).extra(select={'month': dateTrunc("month", "working_date")}).values_list("month").annotate(Sum("charge")).order_by("month"))
        data = convertDictKeyToDate(data)

        for month in timesheetMonths:
            n_days = data.get(month, 0)
            timesheetData.append(n_days)

        timesheetData.append(sum(timesheetData))  # Add total per consultant
        timesheetData.append(timesheetData[-1] * consultant_rates[consultant][0] / 1000)  # Add total in money

        # Forecast staffing data
        staffingData = []
        for month in staffingMonths:
            data = sum([t.charge for t in staffings.filter(consultant=consultant) if (t.staffing_date.month == month.month and t.staffing_date.year == month.year)])
            if timesheetMonths  and \
               date(timesheetMonths[-1].year, timesheetMonths[-1].month, 1) == current_month and \
               date(month.year, month.month, 1) == current_month:
                # Remove timesheet days from current month forecast days
                data -= timesheetData[-3]  # Last is total in money, the one before is total in days
                if data < 0:
                    data = 0  # If timesheet is superior to forecasted, don't consider negative forecasting staffing
            staffingData.append(data)
        staffingData.append(sum(staffingData))  # Add total per consultant
        staffingData.append(staffingData[-1] * consultant_rates[consultant][0] / 1000)  # Add total in money

        # Estimated (= timesheet + forecast staffing)
        estimatedData = (timesheetData[-2] + staffingData[-2], timesheetData[-1] + staffingData[-1])
        # Add tuple to data
        missionData.append((consultant, timesheetData, staffingData, estimatedData))

    # Compute the total daily rate for each month of the mission
    timesheetTotalAmount = []
    staffingTotalAmount = []
    for consultant, timesheet, staffing, estimated in missionData:
        rate = consultant_rates[consultant][0]
        # We don't compute the average rate for total (k€) columns, hence the [:-1]
        valuedTimesheet = [days * rate / 1000 for days in  timesheet[:-1]]
        valuedStaffing = [days * rate / 1000 for days in staffing[:-1]]
        timesheetTotalAmount = map(lambda t, v: (t + v) if t else v, timesheetTotalAmount, valuedTimesheet)
        staffingTotalAmount = map(lambda t, v: (t + v) if t else v, staffingTotalAmount, valuedStaffing)

    # Compute total per month
    timesheetTotal = [timesheet for consultant, timesheet, staffing, estimated in missionData]
    timesheetTotal = zip(*timesheetTotal)  # [ [1, 2, 3], [4, 5, 6]... ] => [ [1, 4], [2, 5], [4, 6]...]
    timesheetTotal = [sum(t) for t in timesheetTotal]
    staffingTotal = [staffing for consultant, timesheet, staffing, estimated in missionData]
    staffingTotal = zip(*staffingTotal)  # [ [1, 2, 3], [4, 5, 6]... ] => [ [1, 4], [2, 5], [4, 6]...]
    staffingTotal = [sum(t) for t in staffingTotal]

    # average = total 1000 * rate / number of billed days
    timesheetAverageRate = map(lambda t, d: (1000 * t / d) if d else 0, timesheetTotalAmount, timesheetTotal[:-1])
    staffingAverageRate = map(lambda t, d: (1000 * t / d) if d else 0, staffingTotalAmount, staffingTotal[:-1])

    # Total estimated (timesheet + staffing)
    if timesheetTotal and staffingTotal:
        estimatedTotal = (timesheetTotal[-2] + staffingTotal[-2], timesheetTotal[-1] + staffingTotal[-1])
    else:
        estimatedTotal = (0, 0)

    if mission.price and timesheetTotal and staffingTotal and mission.billing_mode == "FIXED_PRICE":
        margin = float(mission.price) - timesheetTotal[-1] - staffingTotal[-1]
        margin = to_int_or_round(margin, 3)
        daysTotal = timesheetTotal[-2] + staffingTotal[-2]
        avgDailyRate = int((1000.0 * float(mission.price) / daysTotal)) if daysTotal > 0 else 0
    else:
        margin = 0
        avgDailyRate = 0

    if mission.price and timesheetTotal and staffingTotal and mission.billing_mode == "TIME_SPENT":
        currentUnused = to_int_or_round(float(mission.price) - timesheetTotal[-1], 1)
        forecastedUnused = to_int_or_round(float(mission.price) - timesheetTotal[-1] - staffingTotal[-1], 1)
    else:
        currentUnused = 0
        forecastedUnused = 0

    missionData.append((None, timesheetTotal, staffingTotal, estimatedTotal,
                        timesheetTotalAmount[:-1], staffingTotalAmount[:-1],  # We remove last one not to  display total twice
                        timesheetAverageRate, staffingAverageRate))

    missionData = map(to_int_or_round, missionData)

    objectiveMargin = mission.objectiveMargin(endDate=nextMonth(current_month))

    # Prepare data for graph
    isoTimesheetDates = [t.isoformat() for t in timesheetMonths]
    if len(timesheetMonths) > 0:
        minDate = previousMonth(timesheetMonths[0]).isoformat()
    else:
        minDate = previousMonth(date.today()).isoformat()
    isoStaffingDates = [t.isoformat() for t in staffingMonths]
    if len(isoStaffingDates) > 0 and len(isoTimesheetDates) > 0:
        if isoTimesheetDates[-1] == isoStaffingDates[0]:
            # We have an overlap
            isoDates = isoTimesheetDates + isoStaffingDates[1:]
            graph_timesheet = timesheetTotalAmount[:-1] + [0,]*len(isoStaffingDates[1:])
            graph_staffing = [0,]*len(isoTimesheetDates[:-1]) + staffingTotalAmount[:-1]
        else:
            # Both timesheet and staffing but no overlap
            isoDates = isoTimesheetDates + isoStaffingDates
            graph_timesheet = timesheetTotalAmount[:-1] +  [0,]*len(isoStaffingDates)
            graph_staffing = [0,]*len(isoTimesheetDates) + staffingTotalAmount[:-1]
    else:
        # Only timesheet or staffing
        isoDates = isoTimesheetDates + isoStaffingDates
        graph_timesheet = timesheetTotalAmount[:-1]
        graph_staffing = [0,]*len(isoTimesheetDates) + staffingTotalAmount[:-1]

    graph_data = [["dataTimesheet"] + to_int_or_round(cumulateList(graph_timesheet)),
                  ["dataStaffing"] + to_int_or_round(cumulateList(graph_staffing)),
                  ["dates"] + isoDates]

    return render(request, "staffing/mission_timesheet.html",
                  {"mission": mission,
                   "margin": margin,
                   "objective_margin": objectiveMargin,
                   "objective_margin_total": sum(objectiveMargin.values()),
                   "forecasted_unused": forecastedUnused,
                   "current_unused": currentUnused,
                   "timesheet_months": timesheetMonths,
                   "staffing_months": staffingMonths,
                   "mission_data": missionData,
                   "consultant_rates": consultant_rates,
                   "avg_daily_rate": avgDailyRate,
                   "graph_data": json.dumps(graph_data),
                   "graph_data_timesheet": json.dumps(graph_data),
                   "series_colors": COLORS,
                   "min_date" : minDate,
                   "user": request.user})


def mission_csv_timesheet(request, mission, consultants):
    """@return: csv timesheet for a given mission"""
    # This "view" is never called directly but only through consultant_timesheet view
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s.csv" % mission.mission_id()
    writer = csv.writer(response, delimiter=';')
    timesheets = Timesheet.objects.select_related().filter(mission=mission)
    months = timesheets.dates("working_date", "month")

    for month in months:
        days = daysOfMonth(month)
        next_month = nextMonth(month)
        padding = 31 - len(days)  # Padding for month with less than 31 days to align total column
        # Header
        writer.writerow([("%s - %s" % (mission.full_name(), formats.date_format(month, format="YEAR_MONTH_FORMAT"))).encode("ISO-8859-15", "replace"), ])

        # Days
        writer.writerow(["", ] + [d.day for d in days])
        dayHeader = [_("Consultants").encode("ISO-8859-15", "replace")] + [_(d.strftime("%a")) for d in days]
        if padding:
            dayHeader.extend([""] * padding)
        dayHeader.append(_("total"))
        writer.writerow(dayHeader)

        for consultant in consultants:
            total = 0
            row = [unicode(consultant).encode("ISO-8859-15", "replace"), ]
            consultant_timesheets = {}
            for timesheet in timesheets.filter(consultant_id=consultant.id,
                                               working_date__gte=month,
                                               working_date__lt=next_month):
                consultant_timesheets[timesheet.working_date] = timesheet.charge
            for day in days:
                try:
                    charge = consultant_timesheets.get(day)
                    if charge:
                        row.append(formats.number_format(charge))
                        total += charge
                    else:
                        row.append("")
                except Timesheet.DoesNotExist:
                    row.append("")
            if padding:
                row.extend([""] * padding)
            row.append(formats.number_format(total))
            if total > 0:
                writer.writerow(row)
        writer.writerow([""])
    return response


@pydici_non_public
@pydici_feature("reports")
def all_timesheet(request, year=None, month=None):
    if year and month:
        month = date(int(year), int(month), 1)
    else:
        month = date.today().replace(day=1)  # We use the first day to represent month

    previous_date = (month - timedelta(days=5)).replace(day=1)
    next_date = nextMonth(month)

    timesheets = Timesheet.objects.filter(working_date__gte=month)  # Filter on current month
    timesheets = timesheets.filter(working_date__lt=next_date.replace(day=1))  # Discard next month
    timesheets = timesheets.values("consultant", "mission")  # group by consultant, mission
    timesheets = timesheets.annotate(sum=Sum('charge')).order_by("mission", "consultant")  # Sum and clean order by (else, group by won't work because of default ordering)
    consultants = list(set([i["consultant"] for i in timesheets]))
    missions = list(set([i["mission"] for i in timesheets]))
    consultants = Consultant.objects.filter(id__in=consultants).order_by("name")
    missions = sortMissions(Mission.objects.filter(id__in=missions))
    charges = {}
    if "csv" in request.GET:
        # Simple consultant list
        data = list(consultants)
    else:
        # drill down link
        data = [mark_safe("<a href='%s?year=%s;month=%s;#tab-timesheet'>%s</a>" % (urlresolvers.reverse("people.views.consultant_home", args=[consultant.id]),
                                                                                   month.year,
                                                                                   month.month,
                                                                                   escape(unicode(consultant)))) for consultant in consultants]
    data = [[_("Mission"), _("Mission id")] + data]
    for timesheet in timesheets:
        charges[(timesheet["mission"], timesheet["consultant"])] = to_int_or_round(timesheet["sum"], 2)
    for mission in missions:
        missionUrl = "<a href='%s'>%s</a>" % (urlresolvers.reverse("staffing.views.mission_home", args=[mission.id, ]),
                                        escape(unicode(mission)))
        if "csv" in request.GET:
            # Simple mission name
            consultantData = [unicode(mission), mission.mission_id()]
        else:
            # Drill down link
            consultantData = [mark_safe(missionUrl), mission.mission_id()]
        for consultant in consultants:
            consultantData.append(charges.get((mission.id, consultant.id), 0))
        data.append(consultantData)
    charges = data

    # Compute total per consultant
    if len(charges) > 1:
        total = [i[2:] for i in charges[1:]]
        total = zip(*total)  # [ [1, 2, 3], [4, 5, 6]... ] => [ [1, 4], [2, 5], [4, 6]...]
        total = [sum(t) for t in total]
        charges.append([_("Total"), ""] + total)
    else:
        # Set charges to None to allow proper message on template
        charges = None

    # Add days without lunch ticket
    ticketData = []
    for consultant in consultants:
        lunchTickets = LunchTicket.objects.filter(consultant=consultant)
        lunchTickets = lunchTickets.filter(lunch_date__gte=month).filter(lunch_date__lt=next_date)
        ticketData.append(lunchTickets.count())

    if charges:
        charges.append([_("Days without lunch ticket"), ""] + ticketData)

    #          , Cons1, Cons2, Cons3
    # Mission 1, M1/C1, M1/C2, M1/C3
    # Mission 2, M2/C1, M2/C2, M2/C3
    # with. tk   C1,    C2,    C3...

    if "csv" in request.GET and charges:
        # Return CSV timesheet
        return all_csv_timesheet(request, charges, month)
    else:
        # Return html page
        return render(request, "staffing/all_timesheet.html",
                      {"user": request.user,
                       "next_date": next_date,
                       "previous_date": previous_date,
                       "month": month,
                       "consultants": consultants,
                       "missions": missions,
                       "charges": charges})


@pydici_non_public
@pydici_feature("reports")
def all_csv_timesheet(request, charges, month):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s" % _("timesheet.csv")
    writer = csv.writer(response, delimiter=';')

    # Header
    writer.writerow([unicode(month).encode("ISO-8859-15", "replace"), ])
    for charge in charges:
        row = []
        for i in charge:
            if isinstance(i, float):
                i = formats.number_format(i)
            else:
                i = unicode(i).encode("ISO-8859-15", "replace")
            row.append(i)
        writer.writerow(row)
    return response


@pydici_non_public
@pydici_feature("reports")
def detailed_csv_timesheet(request, year=None, month=None):
    """Detailed timesheet with mission, consultant, and rates
    Intended for accounting third party system or spreadsheet analysis"""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s" % _("timesheet.csv")
    writer = csv.writer(response, delimiter=';')

    if year and month:
        month = date(int(year), int(month), 1)
    else:
        month = date.today().replace(day=1)  # We use the first day to represent month

    next_month = nextMonth(month)

    # Header
    header = [_("Lead"), _("Deal id"), _(u"Lead Price (k€)"), _("Mission"), _("Mission id"), _("Billing mode"), _(u"Mission Price (k€)"),
              _("Consultant"), _("Daily rate"), _("Bought daily rate"), _("Past done days"), _("Done days"), _("Days to be done")]
    writer.writerow([unicode(month).encode("ISO-8859-15", "replace"), ])
    writer.writerow([unicode(i).encode("ISO-8859-15", "replace") for i in header])

    missions = Mission.objects.filter(Q(timesheet__working_date__gte=month, timesheet__working_date__lt=next_month) |
                                      Q(staffing__staffing_date__gte=month, staffing__staffing_date__lt=next_month))
    missions = missions.distinct().order_by("lead")

    for mission in missions:
        for consultant in mission.consultants():
            row = [mission.lead if mission.lead else "", mission.lead.deal_id if mission.lead else "",
                   mission.lead.sales if mission.lead else 0, mission,
                   mission.mission_id(), mission.get_billing_mode_display(),
                   formats.number_format(mission.price) if mission.price else 0, consultant]
            # Rates
            try:
                financialCondition = FinancialCondition.objects.get(consultant=consultant, mission=mission)
                row.append(formats.number_format(financialCondition.daily_rate) if financialCondition.daily_rate else 0)
                row.append(formats.number_format(financialCondition.bought_daily_rate) if financialCondition.bought_daily_rate else 0)
            except FinancialCondition.DoesNotExist:
                row.extend([0, 0])
            # Past timesheet
            timesheet = Timesheet.objects.filter(mission=mission, consultant=consultant,
                                                 working_date__lt=month).aggregate(Sum("charge")).values()[0]
            row.append(formats.number_format(timesheet) if timesheet else 0)
            # Current month timesheet
            timesheet = Timesheet.objects.filter(mission=mission, consultant=consultant,
                                                 working_date__gte=month,
                                                 working_date__lt=next_month).aggregate(Sum("charge")).values()[0]
            row.append(formats.number_format(timesheet) if timesheet else 0)
            # Forecasted staffing
            forecast = Staffing.objects.filter(mission=mission, consultant=consultant,
                                               staffing_date__gte=next_month).aggregate(Sum("charge")).values()[0]
            row.append(formats.number_format(forecast) if forecast else 0)

            writer.writerow([unicode(i).encode("ISO-8859-15", "replace") for i in row])

    return response


@pydici_non_public
@pydici_feature("management")
def holidays_planning(request, year=None, month=None):
    """Display forecasted holidays of all consultants"""
    # We use the first day to represent month
    if year and month:
        month = date(int(year), int(month), 1)
    else:
        month = date.today().replace(day=1)

    holidays_days = Holiday.objects.all().values_list("day", flat=True)
    days = daysOfMonth(month)
    data = []
    # TODO: holidays (jours fériés
    # TODO: week end)

    if date.today().replace(day=1) == month:
        today = datetime.today().day
    else:
        today = 0

    next_month = nextMonth(month)
    previous_month = previousMonth(month)
    for consultant in Consultant.objects.filter(active=True, subcontractor=False):
        consultantData = [consultant, ]
        consultantHolidays = Timesheet.objects.filter(working_date__gte=month, working_date__lt=next_month,
                                                      consultant=consultant, mission__nature="HOLIDAYS", charge__gt=0).values_list("working_date", flat=True)
        for day in days:
            if day.isoweekday() in (6, 7) or day in holidays_days:
                consultantData.append("lightgrey")
            elif day in consultantHolidays:
                consultantData.append("#56160C")
            else:
                consultantData.append("#F6F6F6")
        data.append(consultantData)
    return render(request, "staffing/holidays_planning.html",
                  {"days": days,
                   "data": data,
                   "month": month,
                   "today": today,
                   "previous_month": previous_month,
                   "next_month": next_month,
                   "user": request.user, })


@pydici_non_public
@pydici_feature("leads")
@permission_required("staffing.add_mission")
def create_new_mission_from_lead(request, lead_id):
    """Create a new mission on the given lead. Mission are created with same nature
    and probability than the fist mission.
    Used when a lead has more than one mission as only the default (first) mission
    is created during standard lead workflow.
    An error message will be returned if the given lead does not already have a mission"""
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        raise Http404

    if lead.mission_set.count() == 0:
        # No mission defined, return an error
        return HttpResponse(_("This lead has no mission defined"))

    # We use first mission as model to create to new one
    modelMission = lead.mission_set.all()[0]

    # Create new mission on this lead
    mission = Mission()
    mission.lead = lead
    mission.responsible = lead.responsible
    mission.nature = modelMission.nature
    mission.probability = modelMission.probability
    mission.probability_auto = True
    mission.subsidiary = lead.subsidiary
    mission.save()
    mission.create_default_staffing()  # Initialize default staffing

    # Redirect user to change page of the mission
    # in order to type description and deal id
    return HttpResponseRedirect(urlresolvers.reverse("mission_update", args=[mission.id, ]) + "?return_to=" + lead.get_absolute_url() + "#goto_tab-missions")


@pydici_non_public
def mission_consultant_rate(request):
    """Select or create financial condition for this consultant/mission tuple and update it
    This is intended to be used through a jquery jeditable call"""
    if not (request.user.has_perm("staffing.add_financialcondition") and
        request.user.has_perm("staffing.change_financialcondition")):
        return HttpResponse(_("You are not allowed to do that"))
    try:
        sold, mission_id, consultant_id = request.POST["id"].split("-")
        mission = Mission.objects.get(id=mission_id)
        consultant = Consultant.objects.get(id=consultant_id)
        condition, created = FinancialCondition.objects.get_or_create(mission=mission, consultant=consultant,
                                                                      defaults={"daily_rate": 0})
        if sold == "sold":
            condition.daily_rate = request.POST["value"].replace(" ", "")
        else:
            condition.bought_daily_rate = request.POST["value"].replace(" ", "")
        condition.save()
        return HttpResponse(request.POST["value"])
    except (Mission.DoesNotExist, Consultant.DoesNotExist):
        return HttpResponse(_("Mission or consultant does not exist"))
    except ValueError:
        return HttpResponse(_("Incorrect value"))


@pydici_non_public
@pydici_feature("staffing")
def mission_update(request):
    """Update mission attribute (probability and billing_mode).
    This is intended to be used through a jquery jeditable call"""
    if request.method == "GET":
        # Return authorized values
        if request.GET["id"].startswith("billing_mode"):
            values = Mission.BILLING_MODES
        elif request.GET["id"].startswith("probability"):
            values = Mission.PROBABILITY
        else:
            values = {}
        return HttpResponse(json.dumps(dict(values)))
    elif request.method == "POST":
        # Update mission attributes
        attribute, mission_id = request.POST["id"].split("-")
        value = request.POST["value"]
        mission = Mission.objects.get(id=mission_id)  # If no mission found, it fails, that's what we want
        billingModes = dict(Mission.BILLING_MODES)
        probability = dict(Mission.PROBABILITY)
        if attribute == "billing_mode":
            if value in billingModes:
                mission.billing_mode = value
                mission.save()
                return HttpResponse(billingModes[value])
        elif attribute == "probability":
            value = int(value)
            if value in probability:
                mission.probability = value
                mission.probability_auto = False
                mission.save()
                return HttpResponse(probability[value])
    # Not GET or POST ? Or not explicit attribute ?
    # Do not answer to garbage question, just return
    return


@pydici_non_public
def mission_contacts(request, mission_id):
    """Mission contacts: business, work, administrative
    This views is intented to be called in ajax"""

    mission = Mission.objects.get(id=mission_id)
    if request.method == "POST":
        form = MissionContactsForm(request.POST, instance=mission)
        if form.is_valid():
            form.save()
        return HttpResponseRedirect(urlresolvers.reverse("staffing.views.mission_home", args=[mission.id, ]))

    # Unbound form
    form = MissionContactsForm(instance=mission)
    # TODO: add link to add mission contact
    missionContacts = mission.contacts.select_related().order_by("company")
    return render(request, "staffing/mission_contacts.html",
                  {"mission": mission,
                   "mission_contacts": missionContacts,
                   "mission_contact_form": form})


class MissionUpdate(PydiciNonPublicdMixin, UpdateView):
    model = Mission
    template_name = "core/form.html"
    form_class = MissionForm

    def get_success_url(self):
        return self.request.GET.get('return_to', False) or urlresolvers.reverse_lazy("mission_home", args=[self.object.id, ])


@pydici_non_public
@pydici_feature("reports")
@cache_page(60 * 10)
def graph_timesheet_rates_bar_jqp(request, subsidiary_id=None, team_id=None):
    """Nice graph bar of timesheet prod/holidays/nonprod rates
    @:param subsidiary_id: filter graph on the given subsidiary
    @:param team_id: filter graph on the given team
    @todo: per year, with start-end date"""
    dateTrunc = connections[Timesheet.objects.db].ops.date_trunc_sql  # Shortcut to SQL date trunc function
    data = {}  # Graph data
    natures = [i[0] for i in Mission.MISSION_NATURE]  # Mission natures
    nature_data = {}
    nature_data_days = {}
    holiday_days = [h.day for h in  Holiday.objects.all()]
    graph_data = []

    # Create dict per mission nature
    for nature in natures:
        data[nature] = {}

    # Compute date data
    timesheetStartDate = (date.today() - timedelta(365)).replace(day=1)  # Last year, begin of the month
    timesheetEndDate = nextMonth(date.today())  # First day of next month

    # Filter on scope
    if team_id:
        timesheets = Timesheet.objects.filter(consultant__staffing_manager_id=team_id)
    elif subsidiary_id:
        timesheets = Timesheet.objects.filter(consultant__company_id=subsidiary_id)
    else:
        timesheets = Timesheet.objects.all()

    timesheets = timesheets.filter(consultant__subcontractor=False,
                                   consultant__productive=True,
                                   working_date__gt=timesheetStartDate,
                                   working_date__lt=timesheetEndDate).select_related()

    timesheetMonths = timesheets.dates("working_date", "month")
    isoTimesheetMonths = [d.isoformat() for d in timesheetMonths]

    if not timesheetMonths:
        return HttpResponse('')

    nConsultant = dict(timesheets.extra(select={'month': dateTrunc("month", "working_date")}).values_list("month").annotate(Count("consultant__id", distinct=True)).order_by())
    nConsultant = convertDictKeyToDate(nConsultant)

    for nature in natures:
        nature_data[nature] = []
        nature_data_days[nature] = []
        data = dict(timesheets.filter(mission__nature=nature).extra(select={'month': dateTrunc("month", "working_date")}).values_list("month").annotate(Sum("charge")).order_by("month"))
        data = convertDictKeyToDate(data)
        for month in timesheetMonths:
            nature_data[nature].append(100 * data.get(month, 0) / (working_days(month, holiday_days) * nConsultant.get(month, 1)))
            nature_data_days[nature].append(data.get(month, 0))
        graph_data.append(zip(isoTimesheetMonths, nature_data[nature], nature_data_days[nature]))

    prodRate = []
    for prod, nonprod in zip(nature_data["PROD"], nature_data["NONPROD"]):
        if (prod + nonprod) > 0:
            prodRate.append("%.1f" % (100 * prod / (prod + nonprod)))
        else:
            prodRate.append("0")

    graph_data.append(zip(isoTimesheetMonths, prodRate))

    return render(request, "staffing/graph_timesheet_rates_bar_jqp.html",
                  {"graph_data": json.dumps(graph_data),
                   "min_date": previousMonth(timesheetMonths[0]).isoformat(),
                   "natures_display": [i[1] for i in Mission.MISSION_NATURE],
                   "series_colors": COLORS,
                   "user": request.user})


@pydici_non_public
@cache_page(60 * 10)
def graph_profile_rates_jqp(request, subsidiary_id=None, team_id=None):
    """Sale rate per profil
    @:param subsidiary_id: filter graph on the given subsidiary
    @:param team_id: filter graph on the given team
    @todo: per year, with start-end date"""
    graph_data = []
    avgDailyRate = {}
    nDays = {}
    timesheetStartDate = (date.today() - timedelta(365)).replace(day=1)  # Last year, begin of the month
    timesheetEndDate = nextMonth(date.today())  # First day of next month
    profils = dict(ConsultantProfile.objects.all().values_list("id", "name"))  # Consultant Profiles

    # Create dict per consultant profile
    for profilId in profils.keys():
        avgDailyRate[profilId] = {}
        nDays[profilId] = {}

    # Filter on scope
    if team_id:
        timesheets = Timesheet.objects.filter(consultant__staffing_manager_id=team_id)
    elif subsidiary_id:
        timesheets = Timesheet.objects.filter(consultant__company_id=subsidiary_id)
    else:
        timesheets = Timesheet.objects.all()

    timesheets = timesheets.filter(consultant__subcontractor=False,
                                   consultant__productive=True,
                                   working_date__gt=timesheetStartDate,
                                   working_date__lt=timesheetEndDate).select_related()

    timesheetMonths = timesheets.dates("working_date", "month")
    isoTimesheetMonths = [d.isoformat() for d in timesheetMonths]
    if not timesheetMonths:
        return HttpResponse('')

    financialConditions = {}
    for fc in FinancialCondition.objects.all():
        financialConditions["%s-%s" % (fc.mission_id, fc.consultant_id)] = fc.daily_rate

    for timesheet in timesheets:
        month = date(timesheet.working_date.year, timesheet.working_date.month, 1)
        if not month in avgDailyRate[timesheet.consultant.profil.id]:
            avgDailyRate[timesheet.consultant.profil.id][month] = 0
        if not month in nDays[timesheet.consultant.profil.id]:
            nDays[timesheet.consultant.profil.id][month] = 0

        daily_rate = financialConditions.get("%s-%s" % (timesheet.mission_id, timesheet.consultant_id), 0)
        if daily_rate > 0:
            avgDailyRate[timesheet.consultant.profil.id][month] += timesheet.charge * daily_rate
            nDays[timesheet.consultant.profil.id][month] += timesheet.charge

    for profil in profils.keys():
        data = []
        for month in timesheetMonths:
            if month in nDays[profil] and nDays[profil][month] > 0:
                data.append(avgDailyRate[profil][month] / nDays[profil][month])
            else:
                data.append(None)
        graph_data.append(zip(isoTimesheetMonths, data))

    return render(request, "staffing/graph_profile_rates_jqp.html",
              {"graph_data": json.dumps(graph_data),
               "min_date": previousMonth(timesheetMonths[0]).isoformat(),
               "profils_display": profils.values(),
               "series_colors": COLORS,
               "user": request.user})


@pydici_non_public
@cache_page(60 * 10)
def graph_consultant_rates(request, consultant_id):
    """Nice graph of consultant rates"""
    dailyRateData = []  # Consultant daily rate data
    dailyRateObj = []  # daily rate objective for month
    prodRateData = []  # Consultant production rate data
    prodRateObj = []  # production rate objective for month
    isoRateDates = []  # List of date in iso format for daily rates data
    isoProdDates = []  # List of date in iso format for production rates data
    graph_data = []  # Data that will be returned to jqplot
    consultant = Consultant.objects.get(id=consultant_id)
    startDate = (date.today() - timedelta(24 * 30)).replace(day=1)

    timesheets = Timesheet.objects.filter(consultant=consultant, charge__gt=0, working_date__gte=startDate, working_date__lt=nextMonth(date.today()))
    kdates = list(timesheets.dates("working_date", "month"))

    # Avg daily rate / month and objective rate
    for refDate in kdates:
        next_month = nextMonth(refDate)
        prodRate = consultant.getProductionRate(refDate, next_month)
        if prodRate:
            prodRateData.append(round(100 * prodRate, 1))
            isoProdDates.append(refDate.isoformat())
        fc = consultant.getFinancialConditions(refDate, next_month)
        if fc:
            dailyRateData.append(int(sum([rate * days for rate, days in fc]) / sum([days for rate, days in fc])))
            isoRateDates.append(refDate.isoformat())
        rate = consultant.getRateObjective(refDate, rate_type="DAILY_RATE")
        if rate:
            dailyRateObj.append(rate.rate)
        else:
            dailyRateObj.append(None)
        rate = consultant.getRateObjective(refDate, rate_type="PROD_RATE")
        if rate:
            prodRateObj.append(rate.rate)
        else:
            prodRateObj.append(None)


    graph_data = [
        ["x_daily_rate"] + isoRateDates,
        ["x_prod_rate"] + isoProdDates,
        ["y_daily_rate"] + dailyRateData,
        ["y_prod_rate"] + prodRateData,
        ["y_daily_rate_obj"] + dailyRateObj,
        ["y_prod_rate_obj"] + prodRateObj,
    ]

    return render(request, "staffing/graph_consultant_rate.html",
                  {"graph_data": json.dumps(graph_data),
                   "user": request.user})
