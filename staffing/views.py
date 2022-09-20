# coding: utf-8
"""
Pydici staffing views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta, datetime
import csv
import json
from itertools import zip_longest
import codecs
from collections import defaultdict

from django.core.cache import cache
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.contrib.auth.decorators import permission_required
from django.forms.models import inlineformset_factory
from django.forms import formset_factory
from django.utils.translation import gettext as _
from django.utils.encoding import force_text
from django.urls import reverse, reverse_lazy
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.db import connections, transaction, IntegrityError
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.utils import formats
from django.views.decorators.cache import cache_page, cache_control
from django.utils.decorators import method_decorator
from django.views.generic.edit import UpdateView
from django.contrib import messages
from django.conf import settings
from django.template.loader import get_template

from django_weasyprint import WeasyTemplateView
from auditlog.models import LogEntry

from staffing.models import Staffing, Mission, Holiday, Timesheet, FinancialCondition, LunchTicket
from people.models import Consultant, Subsidiary, RateObjective
from leads.models import Lead
from people.models import ConsultantProfile
from staffing.forms import ConsultantStaffingInlineFormset, MissionStaffingInlineFormset, \
    TimesheetForm, MassStaffingForm, MissionContactsForm, StaffingForm
from core.utils import working_days, nextMonth, previousMonth, daysOfMonth, previousWeek, nextWeek, monthWeekNumber, \
    to_int_or_round, COLORS, cumulateList, user_has_feature, get_parameter, \
    get_fiscal_years_from_qs, get_fiscal_year
from core.decorator import pydici_non_public, pydici_feature, PydiciNonPublicdMixin, pydici_subcontractor
from staffing.utils import gatherTimesheetData, saveTimesheetData, saveFormsetAndLog, \
    sortMissions, holidayDays, staffingDates, time_string_for_day_percent, \
    timesheet_report_data, timesheet_report_data_grouped, check_missions_limited_mode, check_missions_min_charge
from staffing.forms import MissionForm, OptimiserForm, MissionOptimiserForm, MissionOptimiserFormsetHelper
from staffing.optim import solve_pdc, solver_solution_format, compute_consultant_freetime, compute_consultant_rates, solver_apply_forecast
from people.utils import get_team_scopes
from crm.utils import get_subsidiary_from_session
from people.utils import subcontractor_is_user


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
    timesheet_next_month = (timesheet_month + timedelta(days=40)).replace(day=1)
    ontime_editing = (current_month == timesheet_month) or (date.today() - timesheet_next_month).days <= 3

    if (user.has_perm("staffing.add_timesheet") and
            user.has_perm("staffing.change_timesheet") and
            user.has_perm("staffing.delete_timesheet")):
        return TIMESHEET_ACCESS_READ_WRITE

    try:
        trigramme = user.username.upper()
        user_consultant = Consultant.objects.get(trigramme=trigramme)
    except Consultant.DoesNotExist:
        return TIMESHEET_ACCESS_NOT_ALLOWED

    if (user_consultant.id == consultant.id or  # own timesheet
            consultant in user_consultant.team() or  # team timesheet
            (user_has_feature(user, "timesheet_subsidiary") and user_consultant.company == consultant.company)):  # subsidiary timesheet
        # A consultant can only edit timesheet on current month and few days after
        if ontime_editing:
            return TIMESHEET_ACCESS_READ_WRITE
        else:
            return TIMESHEET_ACCESS_READ_ONLY

    # User is accessing the timesheet of another user
    if user_consultant.subcontractor:
        return TIMESHEET_ACCESS_NOT_ALLOWED

    # A user with timesheet_subcontractor can manage subcontractor timesheet
    if consultant.subcontractor and user_has_feature(user, "timesheet_subcontractor"):
        if ontime_editing:
            return TIMESHEET_ACCESS_READ_WRITE
        else:
            return TIMESHEET_ACCESS_READ_ONLY

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
        data_url = reverse('staffing:active_mission_table_DT')
    else:
        data_url = reverse('staffing:all_mission_table_DT')
    return render(request, "staffing/missions.html",
                  {"all": not onlyActive,
                   "data_url": data_url,
                   "datatable_options": ''' "columnDefs": [{ "orderable": false, "targets": [4, 8, 9] },
                                                             { className: "hidden-xs hidden-sm hidden-md", "targets": [6,7,8,9]}],
                                             "order": [[0, "asc"]] ''',
                   "user": request.user})


@pydici_non_public
def mission_home(request, mission_id):
    """Home page of mission description - this page loads all others mission sub-pages"""
    try:
        mission = Mission.objects.get(id=mission_id)
    except Mission.DoesNotExist:
        raise Http404
    return render(request, 'staffing/mission.html',
                  {"mission": mission,
                   "enable_doc_tab": bool(settings.DOCUMENT_PROJECT_PATH),
                   "user": request.user})


@pydici_non_public
def mission_consultants(request, mission_id):
    mission = Mission.objects.get(id=mission_id)
    rates = {}
    objective_rates = mission.consultant_objective_rates()
    for consultant, rate in mission.consultant_rates().items():
        rates[consultant] = (rate, objective_rates.get(consultant))
    try:
        objective_dates = [i[0] for i in list(objective_rates.values())[0]]
    except IndexError:
        # No consultant or no objective on mission timeframe
        objective_dates = []
    return render(request, "staffing/mission_consultants.html",
                  {"mission": mission,
                   "objective_dates": objective_dates,
                   "rates": rates})


@pydici_non_public
@cache_control(no_store=True)
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
        return redirect("staffing:mission_home", mission_id)

    StaffingFormSet = inlineformset_factory(Mission, Staffing,
                                            formset=MissionStaffingInlineFormset,
                                            form=StaffingForm,
                                            fields="__all__")
    mission = Mission.objects.get(id=mission_id)
    if request.method == "POST":
        if readOnly:
            # Readonly users should never go here !
            return HttpResponseRedirect(reverse("core:forbidden"))
        formset = StaffingFormSet(request.POST, instance=mission)
        if formset.is_valid():
            saveFormsetAndLog(formset, request)
            formset = StaffingFormSet(instance=mission)  # Recreate a new form for next update
    else:
        formset = StaffingFormSet(instance=mission)  # An unbound form

    # flush mission cache
    cache.delete("Mission.forecasted_work%s" % mission.id)
    cache.delete("Mission.done_work%s" % mission.id)

    return render(request, 'staffing/mission_staffing.html',
                  {"formset": formset,
                   "mission": mission,
                   "remaining": mission.remaining(mode="target"),
                   "read_only": readOnly,
                   "staffing_dates": staffingDates(),
                   "current_month": datetime.today().strftime("%Y%m"),
                   "user": request.user})


@pydici_non_public
@pydici_feature("staffing")
@cache_control(no_store=True)
def consultant_staffing(request, consultant_id):
    """Edit consultant staffing"""
    consultant = Consultant.objects.get(id=consultant_id)

    if not (request.user.has_perm("staffing.add_staffing") and
            request.user.has_perm("staffing.change_staffing") and
            request.user.has_perm("staffing.delete_staffing")):
        # Only forbid access if the user try to edit someone else staffing
        if request.user.username.upper() != consultant.trigramme:
            return HttpResponseRedirect(reverse("core:forbidden"))

    StaffingFormSet = inlineformset_factory(Consultant, Staffing,
                                            form=StaffingForm,
                                            formset=ConsultantStaffingInlineFormset, fields="__all__")

    if request.method == "POST":
        formset = StaffingFormSet(request.POST, instance=consultant)
        if formset.is_valid():
            try:
                saveFormsetAndLog(formset, request)
                formset = StaffingFormSet(instance=consultant)  # Recreate a new form for next update
            except IntegrityError as e:
                # Corner case when user update one line that clash with constraint on another line that is removed on the same time
                formset.management_form.add_error("", e)
    else:
        formset = StaffingFormSet(instance=consultant)  # An unbound form

    return render(request, 'staffing/consultant_staffing.html',
                  {"formset": formset,
                   "consultant": consultant,
                   "staffing_dates": staffingDates(),
                   "current_month": datetime.today().strftime("%Y%m"),
                   "user": request.user})


@pydici_subcontractor
def consultant_missions(request, consultant_id):
    """List of current consultant mission"""
    consultant = Consultant.objects.get(id=consultant_id)
    if not subcontractor_is_user(consultant, request.user):
        # subcontractor cannot see other people page
        return HttpResponseRedirect(reverse("core:forbidden"))

    return render(request, "staffing/consultant_missions.html", {"consultant": consultant})


@pydici_non_public
@pydici_feature("staffing_mass")
@cache_control(no_cache=True)
def mass_staffing(request):
    """Massive staffing form"""
    staffing_dates = [(i, formats.date_format(i, format="YEAR_MONTH_FORMAT")) for i in staffingDates(format="datetime", n=24)]
    now = datetime.now().replace(microsecond=0)  # Remove useless microsecond that pollute form validation in callback
    subsidiary = get_subsidiary_from_session(request)
    if request.method == 'POST':  # If the form has been submitted...
        form = MassStaffingForm(request.POST, staffing_dates=staffing_dates)
        if form.is_valid():  # All validation rules pass
            # Process the data in form.cleaned_data
            if form.cleaned_data["all_consultants"]:
                # Get all active, productive non subcontractors consultants
                consultants = Consultant.objects.filter(active=True, productive=True, subcontractor=False)
                if subsidiary:
                    consultants = consultants.filter(company=subsidiary)
            else:
                # Use selected consultants
                consultants = form.cleaned_data["consultants"]
            for mission in form.cleaned_data["missions"]:
                for consultant in consultants:
                    for staffing_date in form.cleaned_data["staffing_dates"]:
                        staffing_date = date(*[int(i) for i in staffing_date.split("-")])
                        if mission.start_date and staffing_date < mission.start_date.replace(day=1):
                            messages.add_message(request, messages.INFO, _(
                                "Staffing has been ignored for mission %(mission_name)s because %(staffing_date)s is before mission start (%(start_date)s)" % {
                                    "mission_name": mission.short_name(),
                                    "staffing_date": staffing_date,
                                    "start_date": mission.start_date}))
                            continue
                        if mission.end_date and staffing_date > mission.end_date:
                            messages.add_message(request, messages.INFO, _(
                                "Staffing has been ignored for mission %(mission_name)s because %(staffing_date)s is after mission end (%(end_date)s)" % {
                                    "mission_name": mission.short_name(),
                                    "staffing_date": staffing_date,
                                    "end_date": mission.end_date}))
                            continue

                        staffing, created = Staffing.objects.get_or_create(consultant=consultant,
                                                                           mission=mission,
                                                                           staffing_date=staffing_date,
                                                                           defaults={"consultant": consultant,
                                                                                     "mission": mission,
                                                                                     "staffing_date": staffing_date})
                        staffing.charge = form.cleaned_data["charge"]
                        staffing.comment = form.cleaned_data["comment"]
                        staffing.update_date = now
                        staffing.last_user = str(request.user)
                        staffing.save()
            # Redirect to self to display a new unbound form
            messages.add_message(request, messages.INFO, _("Staffing has been updated"))
            return HttpResponseRedirect(reverse("staffing:mass_staffing"))
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
    - n_month: number of month to display in forceast
    - projection: projection mode (nonce, balanced, full) used to filter still-not-won leads"""

    team = None
    subsidiary = get_subsidiary_from_session(request)

    # Various projections modes. Value is ("short name", "description")
    projections = {"none": (_("Only won leads"), _("Only consider won leads for staffing forecasting")),
                   "balanced": (_("Balanced staffing projection"), _(u"Add missions forcecast staffing even if still not won with a ponderation based on the mission won probability")),
                   "full": (_("Full staffing projection"), _("Add missions forcecast staffing even if still not won without any ponderation. All forecast is considered."))}

    # Group by modes. Value is label
    groups = {"manager": _("Group by Manager"),
              "level": _("Group by Level")}

    # Get team
    if "team_id" in request.GET:
        team = Consultant.objects.get(id=int(request.GET["team_id"]))

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

    n_month = 4  # Default number of month to display

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

    month = start_date
    for i in range(n_month):
        months.append(month)
        month = nextMonth(month)

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
    if subsidiary:
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
            for current_staffing in current_staffings.select_related("mission__lead__client__organisation__company"):
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
            available_displayed = to_int_or_round(available_month[month] - (prod_round + unprod_round + holidays_round))
            staffing[consultant].append([prod_round, unprod_round, holidays_round, available_displayed])
            total[month]["prod"] += prod
            total[month]["unprod"] += unprod
            total[month]["holidays"] += holidays
            total[month]["available"] += available
            total[month]["total"] += available_month[month]
        # Add client synthesis to staffing dict
        company = set([m.lead.client.organisation.company for m in list(missions) if m.lead is not None])
        client_list = ", ".join(["<a href='%s'>%s</a>" %
                                (reverse("crm:company_detail", args=[c.id]), escape(c)) for c in company])
        client_list = mark_safe("<div class='hidden-xs hidden-sm'>%s</div>" % client_list)
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
        rates.append(list(map(to_int_or_round, rate)))

    # Format total dict into list
    total = list(total.items())
    total.sort(key=lambda x: x[0])  # Sort according date
    # Remove date, and transform dict into ordered list:
    total = [(to_int_or_round(i[1]["prod"]),
            to_int_or_round(i[1]["unprod"]),
            to_int_or_round(i[1]["holidays"]),
            to_int_or_round(i[1]["total"] - (to_int_or_round(i[1]["prod"]) + to_int_or_round(i[1]["unprod"]) + to_int_or_round(i[1]["holidays"])))) for i in total]

    # Order staffing list
    staffing = list(staffing.items())
    staffing.sort(key=lambda x: x[0].name)  # Sort by name
    if groupby == "manager":
        staffing.sort(key=lambda x: str(x[0].staffing_manager))  # Sort by staffing manager
    else:
        staffing.sort(key=lambda x: x[0].profil.level)  # Sort by level

    scopes, team_current_filter, team_current_url_filter = get_team_scopes(subsidiary, team)
    if team:
        team_name = _("team %(manager_name)s") % {"manager_name": team}
    else:
        team_name = None

    return render(request, "staffing/pdc_review.html",
                  {"staffing": staffing,
                   "months": months,
                   "total": total,
                   "rates": rates,
                   "user": request.user,
                   "projection": projection,
                   "projection_label": projections[projection][0],
                   "projections": projections,
                   "previous_slice_date": previous_slice_date,
                   "next_slice_date": next_slice_date,
                   "start_date": start_date,
                   "groupby": groupby,
                   "groupby_label": groups[groupby],
                   "groups": groups,
                   "scope": team_name or subsidiary or _("Everybody"),
                   "team_current_filter" : team_current_filter,
                   "team_current_url_filter": team_current_url_filter,
                   "scopes": scopes})


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
    total = staffings.aggregate(Sum("charge"))["charge__sum"] or 0
    available = working_days(month, holidays=holidayDays(month), upToToday=False) - total
    return render(request, "staffing/pdc_detail.html",
                  {"staffings": staffings,
                   "total": total,
                   "available": available,
                   "user": request.user})


@pydici_non_public
@pydici_feature("reports")
def prod_report(request, year=None, month=None):
    """Report production by each people and team for each month"""
    team = None
    subsidiary = get_subsidiary_from_session(request)
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

    # Filter on scope
    consultants = Consultant.objects.filter(productive=True).filter(subcontractor=False, timesheet__working_date__gte=start_date).distinct().select_related("staffing_manager")
    if team:
        consultants = consultants.filter(staffing_manager=team)
    if subsidiary:
        consultants = consultants.filter(company=subsidiary)

    holidays_days = Holiday.objects.filter(day__gte=start_date, day__lte=nextMonth(end_date)).values_list("day", flat=True)
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
                daily_rate_obj = consultant.get_rate_objective(working_date=month, rate_type="DAILY_RATE").rate
                prod_rate_obj = float(
                    consultant.get_rate_objective(working_date=month, rate_type="PROD_RATE").rate) / 100
                forecast = int(daily_rate_obj * prod_rate_obj * (month_days - consultant_days.get("HOLIDAYS",0)))
            except AttributeError:
                prod_rate_obj = daily_rate_obj = forecast = 0  # At least one rate objective is missing
            turnover = int(consultant.get_turnover(month, upperBound))
            if turnover == 0 and not consultant.active:
                forecast = 0  # Remove forecast for consultant that leave during the period
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
        forecast = totalForecasted.get(month, 0)
        turnover = totalDone.get(month, 0)
        if forecast > turnover:
            status = all_status["ko"]
        else:
            status = all_status["ok"]
        totalData.append([status, "", [formats.number_format(turnover), formats.number_format(forecast)]])
    data.append([None, totalData])

    # Get team scopes
    scopes, team_current_filter, team_current_url_filter = get_team_scopes(subsidiary, team)
    if team:
        team_name = _("team %(manager_name)s") % {"manager_name": team}
    else:
        team_name = None

    return render(request, "staffing/prod_report.html",
                  {"data": data,
                   "months": months,
                   "end_date": end_date,
                   "previous_slice_date": previous_slice_date,
                   "next_slice_date": next_slice_date,
                   "scope": team_name or  subsidiary or _("Everybody"),
                   "team_current_filter": team_current_filter,
                   "team_current_url_filter": team_current_url_filter,
                   "scopes": scopes})


@pydici_non_public
@pydici_feature("reports")
def fixed_price_missions_report(request):
    """Report current fixed price mission margin"""
    data = []

    missions = Mission.objects.filter(active=True, nature="PROD", billing_mode="FIXED_PRICE")

    subsidiary = get_subsidiary_from_session(request)

    # Filter on subsidiary
    if subsidiary:
        missions = missions.filter(subsidiary=subsidiary)

    for mission in missions.select_related():
        current_remaining = round(mission.remaining(), 1)
        target_remaining = round(mission.remaining(mode="target"), 1)
        margin = round(sum(mission.objectiveMargin().values()) / 1000 + target_remaining, 1)
        data.append((mission, round(mission.done_work_k()[1],1), current_remaining, target_remaining, margin))

    return render(request, "staffing/fixed_price_report.html",
                  {"data": data })


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


@cache_control(no_store=True)
def consultant_timesheet(request, consultant_id, year=None, month=None, week=None):
    """Consultant timesheet"""
    management_mode_error = None
    price_updated_missions = []
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

    notAllowed = HttpResponseRedirect(reverse("core:forbidden"))

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
    missions = set(list(consultant.forecasted_missions(month=month).select_related("lead__client__organisation__company")) +
                   list(consultant.timesheet_missions(month=month).select_related("lead__client__organisation__company")))
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
            return HttpResponseRedirect(reverse("core:forbidden"))
        form = TimesheetForm(request.POST, days=days, missions=missions, holiday_days=holiday_days, showLunchTickets=not consultant.subcontractor,
                             forecastTotal=forecastTotal, timesheetTotal=timesheetTotal)
        if form.is_valid():  # All validation rules pass
            with transaction.atomic():
                sid = transaction.savepoint()
                # Process the data in form.cleaned_data
                saveTimesheetData(consultant, month, form.cleaned_data, timesheetData)
                limited_mode_offending_missions = check_missions_limited_mode(missions)
                min_charge_offending_missions = check_missions_min_charge(missions, month)
                # Rollback timesheet update if any mission don't pass checks
                if limited_mode_offending_missions:
                    transaction.savepoint_rollback(sid)
                    management_mode_error = _(
                        "Timesheet exceeds mission price and management is set as 'limited' (%s)") % ", ".join(
                        [str(m) for m in limited_mode_offending_missions])
                elif min_charge_offending_missions:
                    transaction.savepoint_rollback(sid)
                    management_mode_error = _("Charge cannot be below minimum threshold  (%s)") % ", ".join(
                        [f"{m} : {m.min_charge_per_day} " for m in min_charge_offending_missions])
                else:  # No violation, we can commit timesheet
                    transaction.savepoint_commit(sid)
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

    if request.method == "POST":
        for mission in missions:
            # flush mission cache
            cache.delete("Mission.forecasted_work%s" % mission.id)
            cache.delete("Mission.done_work%s" % mission.id)
            if mission.management_mode == "ELASTIC":
                # Ajust mission and lead price according to done work if needed
                m_days, m_amount = mission.done_work_k()
                if not mission.price:
                    mission.price = 0  # default to 0 if not defined in elastic mode
                if m_amount > mission.price:
                    mission.price = m_amount
                    mission.save()
                    price_updated_missions.append(mission)

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
                   "management_mode_error": management_mode_error,
                   "price_updated_missions": price_updated_missions,
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
    response.write(codecs.BOM_UTF8)  # Poor excel needs tiger bom to understand UTF-8 easily

    writer = csv.writer(response, delimiter=';')

    # Header
    writer.writerow(["%s - %s" % (consultant, month), ])

    # Days
    writer.writerow(["", ""] + [d.day for d in days])
    writer.writerow([_("Mission"), _("Deal id")]
                     + [_(d.strftime("%a")) for d in days] + [_("total")])

    timestring_formatter = TIMESTRING_FORMATTER[settings.TIMESHEET_INPUT_METHOD]

    for mission in missions:
        total = 0
        row = [mission, mission.mission_id()]
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
        return mission_csv_timesheet(request, mission, consultants, end=date.today())
    if "pdf" in request.GET:
        return MissionTimesheetReportPdf.as_view()(request, mission=mission, end=date.today())
    if "csv_grouped" in request.GET:
        return mission_csv_timesheet_grouped(request, mission, consultants, end=date.today())

    if not request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        # This view should only be accessed by ajax request. Redirect lost users
        return redirect("staffing:mission_home", mission_id)

    # Gather timesheet (Only consider timesheet up to today)
    timesheets = Timesheet.objects.filter(mission=mission).filter(working_date__lt=date.today()).order_by("working_date")
    timesheetMonths = list(timesheets.dates("working_date", "month"))

    # Gather forecaster (till current month)
    staffings = Staffing.objects.filter(mission=mission).filter(staffing_date__gte=current_month).order_by("staffing_date")
    staffingMonths = list(staffings.dates("staffing_date", "month"))

    missionData = []  # list of tuple (consultant, (charge month 1, charge month 2), (forecast month 1, forcast month2), estimated)
    for consultant in consultants:
        # Timesheet data
        timesheetData = []
        data = dict(timesheets.filter(consultant=consultant).annotate(month=TruncMonth("working_date")).values_list("month").annotate(Sum("charge")).order_by("month"))

        for month in timesheetMonths:
            n_days = data.get(month, 0)
            timesheetData.append(n_days)

        timesheetData.append(sum(timesheetData))  # Add total per consultant
        timesheetData.append(timesheetData[-1] * consultant_rates[consultant][0] / 1000)  # Add total in money

        # Forecast staffing data
        staffingData = []
        for month in staffingMonths:
            data = sum([t.charge for t in staffings.filter(consultant=consultant) if (t.staffing_date.month == month.month and t.staffing_date.year == month.year)])
            if timesheetMonths and \
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
        timesheetTotalAmount = [sum(x) for x in zip_longest(timesheetTotalAmount, valuedTimesheet, fillvalue=0)]
        staffingTotalAmount = [sum(x) for x in zip_longest(staffingTotalAmount, valuedStaffing, fillvalue=0)]

    # Compute total per month
    timesheetTotal = [timesheet for consultant, timesheet, staffing, estimated in missionData]
    timesheetTotal = zip(*timesheetTotal)  # [ [1, 2, 3], [4, 5, 6]... ] => [ [1, 4], [2, 5], [4, 6]...]
    timesheetTotal = [sum(t) for t in timesheetTotal]
    staffingTotal = [staffing for consultant, timesheet, staffing, estimated in missionData]
    staffingTotal = zip(*staffingTotal)  # [ [1, 2, 3], [4, 5, 6]... ] => [ [1, 4], [2, 5], [4, 6]...]
    staffingTotal = [sum(t) for t in staffingTotal]

    # average = total 1000 * rate / number of billed days
    timesheetAverageRate = list(map(lambda t, d: (1000 * t / d) if d else 0, timesheetTotalAmount, timesheetTotal[:-1]))
    staffingAverageRate = list(map(lambda t, d: (1000 * t / d) if d else 0, staffingTotalAmount, staffingTotal[:-1]))

    # Total estimated (timesheet + staffing)
    if timesheetTotal and staffingTotal:
        estimatedTotal = (timesheetTotal[-2] + staffingTotal[-2], timesheetTotal[-1] + staffingTotal[-1])
    else:
        estimatedTotal = (0, 0)

    # compute margin indicators
    objectiveMargin = mission.objectiveMargin()
    if mission.price and timesheetTotal and staffingTotal:
        currentUnused = to_int_or_round(float(mission.price) - timesheetTotal[-1], 3)
        forecastedUnused = to_int_or_round(float(mission.price) - timesheetTotal[-1] - staffingTotal[-1], 3)
    else:
        currentUnused = 0
        forecastedUnused = 0

    if mission.price and timesheetTotal and staffingTotal and mission.billing_mode == "FIXED_PRICE":
        margin = to_int_or_round(forecastedUnused + sum(objectiveMargin.values())/1000, 3)
        daysTotal = timesheetTotal[-2] + staffingTotal[-2]
        avgDailyRate = int((1000.0 * float(mission.price) / daysTotal)) if daysTotal > 0 else 0
    else:
        margin = 0
        avgDailyRate = 0

    # pad to 8 values
    padded_mission_data = []
    for consultant, timesheet, staffing, estimated in missionData:
        padded_mission_data.append((consultant, timesheet, staffing, estimated, None, None, None, None))
    missionData = padded_mission_data

    # add total
    missionData.append((None, timesheetTotal, staffingTotal, estimatedTotal,
                        timesheetTotalAmount[:-1], staffingTotalAmount[:-1],  # We remove last one not to  display total twice
                        timesheetAverageRate, staffingAverageRate))

    missionData = list(map(to_int_or_round, missionData))

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
            graph_timesheet = timesheetTotalAmount[:-1] + [0,]*len(isoStaffingDates)
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


@pydici_non_public
@pydici_feature("reports")
def mission_csv_timesheet(request, mission, consultants, start=None, end=None):
    """@return: csv timesheet for a given mission"""
    # This "view" is never called directly but only through consultant_timesheet view
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s.csv" % mission.mission_id()
    response.write(codecs.BOM_UTF8)  # Poor excel needs tiger bom to understand UTF-8 easily

    writer = csv.writer(response, delimiter=';')
    for line in timesheet_report_data(mission, padding=True, start=start, end=end):
        writer.writerow(line)

    return response


@pydici_non_public
@pydici_feature("reports")
def mission_csv_timesheet_grouped(request, mission, consultants, start=None, end=None):
    """@return: csv timesheet for a given mission, grouped by daily rate"""
    # This "view" is never called directly but only through consultant_timesheet view
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s.csv" % mission.mission_id()
    response.write(codecs.BOM_UTF8)  # Poor excel needs tiger bom to understand UTF-8 easily

    writer = csv.writer(response, delimiter=';')
    for line in timesheet_report_data_grouped(mission, start=start, end=end):
        writer.writerow(line)

    return response


class MissionTimesheetReportPdf(PydiciNonPublicdMixin, WeasyTemplateView):
    template_name = 'staffing/mission_timesheet_report.html'

    def get_context_data(self, **kwargs):
        context = super(MissionTimesheetReportPdf, self).get_context_data(**kwargs)
        self.mission = self.kwargs["mission"]
        context["mission"] = self.mission
        context["timesheet_data"] = timesheet_report_data(self.mission, padding=True,
                                                          start=self.kwargs.get("start"),
                                                          end=self.kwargs.get("end"))
        return context

    @method_decorator(pydici_feature("reports"))
    def dispatch(self, *args, **kwargs):
        return super(MissionTimesheetReportPdf, self).dispatch(*args, **kwargs)


@pydici_non_public
@pydici_feature("reports")
def all_timesheet(request, year=None, month=None):

    # var for filtering
    subsidiary = get_subsidiary_from_session(request)
    timesheets = None

    if year and month:
        month = date(int(year), int(month), 1)
    else:
        month = date.today().replace(day=1)  # We use the first day to represent month

    previous_date = (month - timedelta(days=5)).replace(day=1)
    next_date = nextMonth(month)
    timesheets = Timesheet.objects.filter(working_date__gte=month)
    timesheets = timesheets.filter(working_date__lt=next_date.replace(day=1))  # Discard next month

    if subsidiary:
        timesheets = timesheets.filter(consultant__company=subsidiary)

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
        data = [mark_safe("<a href='%s?year=%s&month=%s#tab-timesheet' class='pydici-tooltip' title='%s'>%s</a>" % (reverse("people:consultant_home", args=[consultant.trigramme]),
                                                                                   month.year,
                                                                                   month.month,
                                                                                   escape(consultant.name),
                                                                                   escape(consultant.trigramme))) for consultant in consultants]
    data = [[_("Mission")] + data]
    for timesheet in timesheets:
        charges[(timesheet["mission"], timesheet["consultant"])] = to_int_or_round(timesheet["sum"], 2)
    for mission in missions:
        mission_data = escape(str(mission))
        missionUrl = "<a href='%s' class='pydici-tooltip' title='%s'>%s</a>" % (reverse("staffing:mission_home", args=[mission.id, ]),
                                        escape(mission.mission_id()),
                                        (mission_data[:75] + '...' if len(mission_data) > 75 else mission_data))

        if "csv" in request.GET:
            # Simple mission name
            consultantData = [mission.full_name()]
        else:
            # Drill down link
            consultantData = [mark_safe(missionUrl)]
        for consultant in consultants:
            consultantData.append(charges.get((mission.id, consultant.id), 0))
        data.append(consultantData)
    charges = data

    # Compute total per consultant
    if len(charges) > 1:
        total = [i[1:] for i in charges[1:]]
        total = zip(*total)  # [ [1, 2, 3], [4, 5, 6]... ] => [ [1, 4], [2, 5], [4, 6]...]
        total = [sum(t) for t in total]
        charges.append([_("Total")] + total)
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
        charges.append([_("Days without lunch ticket")] + ticketData)

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
    response.write(codecs.BOM_UTF8)  # Poor excel needs tiger bom to understand UTF-8 easily

    writer = csv.writer(response, delimiter=';')

    # Header
    writer.writerow([month])
    for charge in charges:
        row = []
        for i in charge:
            if isinstance(i, float):
                i = formats.number_format(i)
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
    response.write(codecs.BOM_UTF8)  # Poor excel needs tiger bom to understand UTF-8 easily

    writer = csv.writer(response, delimiter=';')

    if year and month:
        month = date(int(year), int(month), 1)
    else:
        month = date.today().replace(day=1)  # We use the first day to represent month

    next_month = nextMonth(month)

    # Header
    header = [_("Lead"), _("Deal id"), _("Lead Price (k€)"), _("Mission"), _("Mission id"), _("Billing mode"), _("Mission Price (k€)"),
              _("Consultant"), _("Daily rate"), _("Bought daily rate"), _("Past done days"), _("Done days"), _("Days to be done")]
    writer.writerow([month,])
    writer.writerow(header)

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
                                                 working_date__lt=month).aggregate(Sum("charge"))["charge__sum"]
            row.append(formats.number_format(timesheet) if timesheet else 0)
            # Current month timesheet
            timesheet = Timesheet.objects.filter(mission=mission, consultant=consultant,
                                                 working_date__gte=month,
                                                 working_date__lt=next_month).aggregate(Sum("charge"))["charge__sum"]
            row.append(formats.number_format(timesheet) if timesheet else 0)
            # Forecasted staffing
            forecast = Staffing.objects.filter(mission=mission, consultant=consultant,
                                               staffing_date__gte=next_month).aggregate(Sum("charge"))["charge__sum"]
            row.append(formats.number_format(forecast) if forecast else 0)

            writer.writerow(row)

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

    subsidiary = get_subsidiary_from_session(request)
    holidays_days = Holiday.objects.all().values_list("day", flat=True)
    days = daysOfMonth(month)
    data = []

    if date.today().replace(day=1) == month:
        today = datetime.today().day
    else:
        today = 0

    next_month = nextMonth(month)
    previous_month = previousMonth(month)
    consultants = Consultant.objects.filter(active=True, subcontractor=False)
    if subsidiary:
        consultants = consultants.filter(company=subsidiary)
    for consultant in consultants:
        consultantData = [consultant, ]
        consultantHolidays = Timesheet.objects.filter(working_date__gte=month, working_date__lt=next_month,
                                                      consultant=consultant, mission__nature="HOLIDAYS", charge__gt=0).values_list("working_date", flat=True)
        for day in days:
            if day.isoweekday() in (6, 7) or day in holidays_days:
                consultantData.append("no-holidays")
            elif day in consultantHolidays:
                consultantData.append("in-holidays")
            else:
                consultantData.append("holidays-weekend")
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
@pydici_feature("reports")
def rate_objective_report(request):
    data = []
    consultants = Consultant.objects.filter(productive=True).filter(active=True).filter(subcontractor=False)
    subsidiary = get_subsidiary_from_session(request)
    if subsidiary:
        consultants = consultants.filter(company=subsidiary)
    working_date_current = date.today()
    working_date_next_year = date.today() + timedelta(365)
    for consultant in consultants:
        for horizon, working_date in ((_("current"), working_date_current), (_("next"), working_date_next_year)):
            for rate_type, rate_label in RateObjective.RATE_TYPE:
                rate_objective = consultant.get_rate_objective(working_date=working_date, rate_type=rate_type)
                data.append({
                    _("consultant"): consultant.name,
                    _("subsidiary"): str(consultant.company),
                    _("type"): str(rate_label),
                    _("horizon"): horizon,
                    _("amount"): rate_objective.rate if rate_objective else None
                })
    return render(request, "staffing/rate_objective_report.html", {"data": json.dumps(data),
                                                                 "derivedAttributes": [],})


@pydici_non_public
@pydici_feature("reports")
@cache_page(60*10*10)
def rates_report(request):
    data = []
    fiscal_year_month = int(get_parameter("FISCAL_YEAR_MONTH"))
    current_year = date.today().year
    years = [current_year - 3, current_year - 2,  current_year -1, current_year]
    consultants = Consultant.objects.filter(productive=True, subcontractor=False)
    subsidiary = get_subsidiary_from_session(request)
    if subsidiary:
        consultants = consultants.filter(company=subsidiary)

    consultants = consultants.filter(timesheet__working_date__gte=date(years[0], fiscal_year_month, 1)).distinct()

    for year in years:
        start_date = date(year, fiscal_year_month, 1)
        end_date = date(year + 1, fiscal_year_month, 1)
        for consultant in consultants:
            amount = 100 * consultant.get_production_rate(start_date=start_date, end_date=end_date)
            if amount:
                data.append({
                    _("consultant"): consultant.name,
                    _("profile"): str(consultant.profil),
                    _("subsidiary"): str(consultant.company),
                    _("type"): _("production rate"),
                    _("year"): year,
                    _("amount"): amount
            })
            prod_days = Timesheet.objects.filter(consultant=consultant,
                                                 charge__gt=0,
                                                 working_date__gte=start_date,
                                                 working_date__lt=end_date,
                                                 mission__nature="PROD").aggregate(Sum("charge"))["charge__sum"]
            turnover = consultant.get_turnover(start_date=start_date, end_date=end_date)
            if turnover > 0 and prod_days:
                data.append({
                    _("consultant"): consultant.name,
                    _("profile"): str(consultant.profil),
                    _("subsidiary"): str(consultant.company),
                    _("type"): _("daily rate"),
                    _("year"): year,
                    _("amount"): turnover / prod_days
            })
    return render(request, "staffing/rates_report.html", {"data": json.dumps(data),
                                                          "derivedAttributes": [],})

@pydici_non_public
@pydici_feature("reports")
def missions_report(request, year=None, nature="HOLIDAYS"):
    """Reports about holidays or non-prod missions"""
    data = []
    dateTrunc = connections[Timesheet.objects.db].ops.date_trunc_sql  # Shortcut to SQL date trunc function
    month = int(get_parameter("FISCAL_YEAR_MONTH"))

    timesheets = Timesheet.objects.filter(mission__nature=nature, working_date__lte=date.today())
    subsidiary = get_subsidiary_from_session(request)
    if subsidiary:
        timesheets = timesheets.filter(consultant__company=subsidiary)


    years = get_fiscal_years_from_qs(timesheets, "working_date")

    if not years:
        return HttpResponse()

    if year is None and years:
        year = years[-1]

    if year != "all":
        year = int(year)
        start = date(year, month, 1)
        end = date(year+1, month, 1)
        timesheets = timesheets.filter(working_date__gte=start, working_date__lt=end)

    timesheets =timesheets.extra(select={'month': dateTrunc("month", "working_date")})
    timesheets = timesheets.values("month", "mission__description", "consultant__name", "consultant__profil__name", "consultant__company__name").annotate(Sum("charge")).order_by("month")

    for timesheet in timesheets:
        # Thank you sqlite for those sad lines of code
        month = timesheet["month"]
        if month and isinstance(month, (datetime, date)):
            month = month.strftime("%Y-%m")
        data.append({
            _("month") : month,
            _("type"): timesheet["mission__description"],
            _("consultant"): timesheet["consultant__name"],
            _("subsidiary"): timesheet["consultant__company__name"],
            _("profil"): timesheet["consultant__profil__name"],
            _("days"): timesheet["charge__sum"],
        })

    return render(request, "staffing/missions_report.html", {"data": json.dumps(data),
                                                             "years": years,
                                                             "selected_year": year,
                                                             "nature": nature,
                                                             "derivedAttributes": [],})



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
    return HttpResponseRedirect(reverse("staffing:mission_update", args=[mission.id, ]) + "?return_to=" + lead.get_absolute_url() + "#goto_tab-missions")


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
        value = request.POST["value"].replace(" ", "")
        if sold == "sold":
            change = {_(f"daily rate for {consultant}"): [condition.daily_rate, value]}
            condition.daily_rate = value
        else:
            change = {_(f"bought daily rate for {consultant}"): [condition.daily_rate, value]}
            condition.bought_daily_rate = value
        condition.save()
        LogEntry.objects.log_create(instance=mission, actor=request.user, action=LogEntry.Action.UPDATE, changes=json.dumps(change))

        return HttpResponse(request.POST["value"])
    except (Mission.DoesNotExist, Consultant.DoesNotExist):
        return HttpResponse(_("Mission or consultant does not exist"))
    except ValueError:
        return HttpResponse(_("Incorrect value"))


@pydici_non_public
@pydici_feature("staffing")
def mission_update(request):
    """Update mission attribute (probability, billing_mode and management mode).
    This is intended to be used through a jquery jeditable call"""
    if request.method == "GET":
        # Return authorized values
        attribute, mission_id = request.GET["id"].split("-")
        mission = Mission.objects.get(id=mission_id)  # If no mission found, it fails, that's what we want
        if attribute == "billing_mode":
            values = dict(Mission.BILLING_MODES)
            if mission.management_mode == "ELASTIC":
                del values["FIXED_PRICE"]
        elif attribute == "management_mode":
            values = dict(Mission.MANAGEMENT_MODES)
            if mission.billing_mode == "FIXED_PRICE":
                del values["ELASTIC"]
        elif attribute == "probability":
            values = dict(Mission.PROBABILITY)
        else:
            values = {}
        return HttpResponse(json.dumps(values))
    elif request.method == "POST":
        # Update mission attributes
        attribute, mission_id = request.POST["id"].split("-")
        value = request.POST["value"]
        mission = Mission.objects.get(id=mission_id)  # If no mission found, it fails, that's what we want
        billingModes = dict(Mission.BILLING_MODES)
        managementModes = dict(Mission.MANAGEMENT_MODES)
        probability = dict(Mission.PROBABILITY)
        if attribute == "billing_mode":
            if value in billingModes:
                mission.billing_mode = value
                mission.save()
        elif attribute == "management_mode":
            if value in managementModes:
                mission.management_mode = value
                mission.save()
                return HttpResponse(managementModes[value])
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
    This views is intended to be called in ajax"""

    mission = Mission.objects.get(id=mission_id)
    if request.method == "POST":
        form = MissionContactsForm(request.POST, instance=mission)
        if form.is_valid():
            form.save()
        return HttpResponseRedirect(reverse("staffing:mission_home", args=[mission.id, ]))

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
        return self.request.GET.get('return_to', False) or reverse_lazy("staffing:mission_home", args=[self.object.id, ])


@pydici_non_public
@pydici_feature("staffing_mass")
def optimise_pdc(request):
    """Propose optimised mission staffing according to business rules"""
    if date.today().day  > 20:
        start_date = nextMonth(date.today())
    else:
        start_date = date.today().replace(day=1)
    staffing_dates = [(i, formats.date_format(i, format="b y")) for i in
                      staffingDates(format="datetime", n=8, minDate=start_date)]
    scores_data = []
    total_score = -1
    results = []
    missions_remaining_results = []
    error = ""
    MissionOptimiserFormset = formset_factory(MissionOptimiserForm, extra=3, can_delete=True)
    solver = None

    if request.method == "POST":
        form = OptimiserForm(request.POST, subsidiary=get_subsidiary_from_session(request))
        formset = MissionOptimiserFormset(request.POST, form_kwargs={"staffing_dates": staffing_dates})
        if form.is_valid() and formset.is_valid():
            # Process the data in form.cleaned_data
            solver_param = {"senior_quota": int(form["senior_quota"].value()),
                            "newbie_quota": int(form["newbie_quota"].value()),
                            "planning_weight": int(form["planning_weight"].value()),
                            "freetime_weight": int(form["freetime_weight"].value()),
                            "mission_per_people_weight": int(form["mission_per_people_weight"].value()),
                            "people_per_mission_weight": int(form["people_per_mission_weight"].value()),}
            missions_charge = {}
            predefined_assignment = {}
            exclusions = {}
            missions_boundaries = {}
            missions = []
            missions_id = []
            for mission_form in formset.cleaned_data:
                if mission_form and not mission_form["DELETE"]:
                    missions_charge[mission_form["mission"].mission_id()] = {month[1]:mission_form["charge_%s" % month[1]] or 0 for month in staffing_dates}
                    missions_id.append(mission_form["mission"].mission_id())
                    missions.append(mission_form["mission"])
                    missions_boundaries[mission_form["mission"].mission_id()] = {"start": formats.date_format(mission_form["mission"].start_date, format="b y") if mission_form["mission"].start_date else None,
                                                                                 "end": formats.date_format(mission_form["mission"].end_date, format="b y") if mission_form["mission"].end_date else None}
                    if mission_form["predefined_assignment"]:
                        predefined_assignment[mission_form["mission"].mission_id()] = [c.trigramme for c in mission_form["predefined_assignment"]]
                        if not set(c.trigramme for c in mission_form["predefined_assignment"]).issubset(set(c.trigramme for c in form.cleaned_data["consultants"])):
                            error = _("Predefined assignment must be in consultant list")
                    if mission_form["exclusions"]:
                        exclusions[mission_form["mission"].mission_id()] = [c.trigramme for c in mission_form["exclusions"]]
                        if not set(c.trigramme for c in mission_form["exclusions"]).issubset(set(c.trigramme for c in form.cleaned_data["consultants"])):
                            error = _("Excluded consultant must be in consultant list")

            consultants_freetime = compute_consultant_freetime(form.cleaned_data["consultants"], missions, staffing_dates, projections=form.cleaned_data["projections"])
            consultant_rates = compute_consultant_rates(form.cleaned_data["consultants"], missions)
            missions_remaining = {m.mission_id():int(1000 * m.remaining()) for m in missions}
            if not error:
                solver, status, scores, staffing = solve_pdc([c.trigramme for c in form.cleaned_data["consultants"]],
                                                              [c.trigramme for c in form.cleaned_data["consultants"] if c.profil.level > 2],
                                                              missions_id, [month[1] for month in staffing_dates],
                                                              missions_charge, missions_remaining, missions_boundaries, consultants_freetime,
                                                              predefined_assignment, exclusions, consultant_rates, solver_param)
                if status:
                    scores_data = [(score.Name(), solver.Value(score)) for score in scores]
                    total_score = sum(solver.Value(score) for score in scores)
                    results, missions_remaining_results = solver_solution_format(solver, staffing, form.cleaned_data["consultants"], missions, staffing_dates,
                                                                                 missions_charge, consultants_freetime, consultant_rates)

                    if "action_update" in request.POST:
                        solver_apply_forecast(solver, staffing, form.cleaned_data["consultants"], missions, staffing_dates, request.user)
                else:
                    error = _("There's no solution. Add consultants, remove mission, exclusions or relax experience ratio constraint")
            # recreate a new formset for further editing with updated charge, based on previous one, removing previous extra forms
            formset = MissionOptimiserFormset(initial=[i for i in formset.cleaned_data if i and not i["DELETE"]], form_kwargs={"staffing_dates": staffing_dates})
            # recreate a new form for further editing with updated consultants list.
            form = OptimiserForm(initial=form.cleaned_data, subsidiary=get_subsidiary_from_session(request))
    else:
        # An unbound form with optional initial data
        consultants = []
        missions = []
        try:
            if "missions" in request.GET:
                missions = [Mission.objects.get(id=int(m)) for m in request.GET.getlist("missions")]
            if "consultants" in request.GET:
                consultants = [Consultant.objects.get(trigramme=c) for c in request.GET.getlist("consultants")]
        except Exception:
            pass # User give garbage as in put
        # complete consultants list with already staffed people
        [consultants.extend(m.consultants()) for m in missions]
        # Create form and formset with optional initial data
        form = OptimiserForm(initial={"consultants": consultants}, subsidiary=get_subsidiary_from_session(request))
        formset = MissionOptimiserFormset(form_kwargs={"staffing_dates": staffing_dates},
                                          initial=[{"mission":m, "predefined_assignment": m.consultants()} for m in missions])

    return render(request, "staffing/optimise_pdc.html",
                  {"form": form,
                   "formset": formset,
                   "formset_helper": MissionOptimiserFormsetHelper(),
                   "scores": scores_data,
                   "total_score": total_score,
                   "results": results,
                   "missions_remaining_results": missions_remaining_results,
                   "error": error,
                   "solver" : solver,
                   "staffing_dates": staffing_dates})


@pydici_non_public
@pydici_feature("reports")
@cache_page(60 * 60 * 10)
def turnover_pivotable(request, year=None):
    """Turnover analysis (per people and mission) based on timesheet production"""
    data = []
    month = int(get_parameter("FISCAL_YEAR_MONTH"))
    missions = Mission.objects.filter(nature="PROD")
    total_turnover = defaultdict(int)

    if not missions:
        return HttpResponse()

    subsidiaries = Subsidiary.objects.all()
    current_subsidiary = get_subsidiary_from_session(request)
    if current_subsidiary:
        subsidiaries = subsidiaries.filter(id=current_subsidiary.id)

    years = get_fiscal_years_from_qs(missions, "lead__creation_date")

    if year is None and years:
        year = years[-1]
    if year != "all":
        year = int(year)
        start = date(year, month, 1)
        end = date(year + 1, month, 1)
        end = min(end, date.today())
        missions = missions.filter(timesheet__working_date__gte=start, timesheet__working_date__lt=end)

    missions = missions.distinct()
    missions = missions.select_related("responsible", "lead__client__contact", "lead__client__organisation__company", "subsidiary",
                         "lead__business_broker__company", "lead__business_broker__contact")

    for mission in missions:
        mission_data = {_("deal id"): mission.lead.deal_id if mission.lead else mission.id,
                         _("name"): mission.short_name(),
                         _("client organisation"): str(mission.lead.client.organisation) if mission.lead else "-",
                         _("client company"): str(mission.lead.client.organisation.company) if mission.lead else "-",
                         _("responsible"): str(mission.responsible),
                         _("billing mode"): mission.get_billing_mode_display(),
                         _("broker"): str(mission.lead.business_broker or _("Direct")) if mission.lead else _("Direct"),
                         _("subsidiary"): str(mission.subsidiary)}
        for month in mission.timesheet_set.dates("working_date", "month", order="ASC"):
            fiscal_year = get_fiscal_year(month)
            if year != "all" and (month < start or month >= end):
                continue  # Skip mission if outside period
            next_month = nextMonth(month)
            if (current_subsidiary and current_subsidiary.id == mission.subsidiary.id) or current_subsidiary is None:
                mission_month_data = mission_data.copy()
                own_turnover = int(mission.done_work_period(month, next_month, include_external_subcontractor=False,
                                                                               include_internal_subcontractor=False)[1])
                turnover_with_external_subcontractor = int(mission.done_work_period(month, next_month,
                                                                                    include_external_subcontractor=True,
                                                                                    include_internal_subcontractor=False)[1])
                turnover_with_internal_subcontractor = int(mission.done_work_period(month, next_month,
                                                                                    include_external_subcontractor=False,
                                                                                    include_internal_subcontractor=True)[1])
                mission_month_data[_("turnover (€)")] = turnover_with_external_subcontractor + turnover_with_internal_subcontractor - own_turnover
                mission_month_data[_("external subcontractor turnover (€)")] = turnover_with_external_subcontractor - own_turnover
                mission_month_data[_("internal subcontractor turnover (€)")] = turnover_with_internal_subcontractor - own_turnover
                mission_month_data[_("own turnover (€)")] = own_turnover
                mission_month_data[_("month")] = month.isoformat()
                mission_month_data[_("fiscal year")] = fiscal_year
                data.append(mission_month_data)
                total_turnover[mission_month_data[_("client company")]] += mission_month_data[_("turnover (€)")]
            # Handle internal subcontractor for this mission
            for subsidiary in subsidiaries.exclude(id=mission.subsidiary_id):
                subsidiary_month_data = mission_data.copy()
                subsidiary_month_data[_("subsidiary")] = str(subsidiary)
                subsidiary_month_data[_("month")] = month.isoformat()
                subsidiary_month_data[_("fiscal year")] = fiscal_year
                subsidiary_turnover = int(mission.done_work_period(month, next_month, include_external_subcontractor=False,
                                                                   filter_on_subsidiary=subsidiary)[1])
                if subsidiary_turnover > 0:
                    subsidiary_month_data[_("own turnover (€)")] = subsidiary_turnover
                    data.append(subsidiary_month_data)

    # Mark top companies
    top_companies = [k for k,v in sorted(total_turnover.items(), key=lambda item: item[1], reverse=True)][:8]
    for d in data:
        if d[_("client company")] in top_companies:
            d[_("top client company")] = d[_("client company")]
        else:
            d[_("top client company")] = _("others")

    return render(request, "staffing/turnover_pivotable.html", { "data": json.dumps(data),
                                                    "derivedAttributes": "{}",
                                                    "years": years,
                                                    "selected_year": year})


@pydici_non_public
@pydici_feature("reports")
def lunch_tickets_pivotable(request):
    """report due tickets on last 12 months
    We consider working days of current month and holidays and days without tickets of previous one"""
    data = []
    start_date = (date.today() - timedelta(30*12)).replace(day=1)

    no_tickets = LunchTicket.objects.filter(lunch_date__gte=start_date, no_ticket=True).annotate(month=TruncMonth("lunch_date")).order_by()
    no_tickets = no_tickets.values("month", "consultant").annotate(Count("id"))
    no_tickets = {(i["consultant"], i["month"]): i["id__count"] for i in no_tickets}  # Switch to dict with (consultant, month) as key

    timesheets = Timesheet.objects.filter(working_date__gte=start_date, working_date__lt=nextMonth(date.today().replace(day=1)), mission__nature="HOLIDAYS")
    timesheets = timesheets.annotate(month=TruncMonth("working_date"))
    timesheets = timesheets.order_by().values("month", "consultant__name", "consultant_id", "consultant__company__name")
    days_off = timesheets.filter(charge__gte=0.5).annotate(Count("id")) # Each days beyond half is counted as 1
    days_off = {(i["consultant_id"], i["month"]): i["id__count"] for i in days_off}  # Switch to dict with (consultant, month) as key

    holidays_days = Holiday.objects.filter(day__gte=start_date).values_list("day", flat=True)
    month = start_date
    w_days = {}
    while month < date.today():
        next_month = nextMonth(month)
        w_days = working_days(next_month, holidays=holidays_days)
        current_month_timesheet = Timesheet.objects.filter(working_date__gte=month, working_date__lt=next_month, consultant__subcontractor=False).order_by()
        consultants = current_month_timesheet.values("consultant_id", "consultant__name", "consultant__company__name").distinct()
        for consultant in consultants:
            item = {}
            item[_("month")] = next_month.isoformat()
            item[_("consultant")] = consultant["consultant__name"]
            item[_("subsidiary")] = consultant["consultant__company__name"]
            item[_("days off previous month")] = days_off.get((consultant["consultant_id"], month), 0)
            item[_("days without tickets previous month")] = no_tickets.get((consultant["consultant_id"], month), 0)
            item[_("deserved tickets")] = w_days - item[_("days off previous month")]  - item[_("days without tickets previous month")]
            data.append(item)
        # Increment month for next loop
        month = next_month

    # LunchTicket.
    return render(request, "staffing/lunch_tickets_pivotable.html", {"data": json.dumps(data),
                                                                "derivedAttributes": "{}"})


@pydici_non_public
@pydici_feature("reports")
@cache_page(60 * 60 * 24)
def graph_timesheet_rates_bar(request, team_id=None):
    """Nice graph bar of timesheet prod/holidays/nonprod rates
    @:param team_id: filter graph on the given team
    @todo: per year, with start-end date"""
    data = {}  # Graph data
    natures = [i[0] for i in Mission.MISSION_NATURE]  # Mission natures id
    natures_label = [i[1] for i in Mission.MISSION_NATURE]  # Mission natures label
    nature_data = {}
    holiday_days = [h.day for h in  Holiday.objects.all()]
    graph_data = []

    # Create dict per mission nature
    for nature in natures:
        data[nature] = {}

    # Compute date data
    timesheetStartDate = (date.today() - 3 * timedelta(365)).replace(day=1)  # Last three years
    timesheetEndDate = date.today()

    subsidiary = get_subsidiary_from_session(request)
    # Filter on scope
    if team_id:
        timesheets = Timesheet.objects.filter(consultant__staffing_manager_id=team_id)
    elif subsidiary:
        timesheets = Timesheet.objects.filter(consultant__company=subsidiary)
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

    nConsultant = dict(timesheets.annotate(month=TruncMonth("working_date")).values_list("month").annotate(Count("consultant__id", distinct=True)).order_by())

    for nature, label in zip(natures, natures_label):
        nature_data[nature] = []
        data = dict(timesheets.filter(mission__nature=nature).annotate(month=TruncMonth("working_date")).values_list("month").annotate(Sum("charge")).order_by("month"))
        for month in timesheetMonths:
            nature_data[nature].append(round(100 * data.get(month, 0) / (working_days(month, holiday_days) * nConsultant.get(month, 1)), 1))
        graph_data.append([label] + nature_data[nature])

    prodRate = []
    for prod, nonprod in zip(nature_data["PROD"], nature_data["NONPROD"]):
        if (prod + nonprod) > 0:
            prodRate.append("%.1f" % (100 * prod / (prod + nonprod)))
        else:
            prodRate.append("0")

    graph_data.append([_("production rate")] + prodRate)
    graph_data.append(["x"] + isoTimesheetMonths)

    return render(request, "staffing/graph_timesheet_rates_bar.html",
                  {"graph_data": json.dumps(graph_data),
                   "natures_display": natures_label,
                   "series_colors": COLORS[:3] + ['#333'],  # Use grey for prod rate to ease readibility
                   "user": request.user})


@pydici_non_public
@cache_page(60 * 60 * 24)
def graph_profile_rates(request, team_id=None):
    """Sale rate per profil
    @:param team_id: filter graph on the given team"""
    #TODO: add start/end timeframe
    graph_data = []
    turnover = {}
    nDays = {}
    avgDailyRate = {}
    globalDailyRate = []
    isoTimesheetMonths = []
    timesheetStartDate = (date.today() - 3 * timedelta(365)).replace(day=1)  # Last three years
    timesheetEndDate = nextMonth(date.today())  # First day of next month
    profils = dict(ConsultantProfile.objects.all().values_list("id", "name"))  # Consultant Profiles

    consultants = Consultant.objects.filter(subcontractor=False, productive=True,
                                            timesheet__working_date__gte=timesheetStartDate,
                                            timesheet__working_date__lt=timesheetEndDate)

    subsidiary = get_subsidiary_from_session(request)
    # Filter on scope
    if team_id:
        consultants = consultants.filter(staffing_manager_id=team_id)
    elif subsidiary:
        consultants = consultants.filter(company=subsidiary)

    consultants = consultants.distinct()

    for profil, profilName in profils.items():
        nDays[profil] = {}
        turnover[profil] = {}
        avgDailyRate[profil] = {}

    month = timesheetStartDate
    while month < timesheetEndDate:
        upperBound = min(date.today(), nextMonth(month))
        isoTimesheetMonths.append(month.isoformat())
        monthGlobalNDays = 0
        monthGlobalTurnover = 0
        for consultant in consultants:
            if not month in nDays[consultant.profil_id]:
                nDays[consultant.profil.id][month] = 0
            if not month in turnover[consultant.profil_id]:
                turnover[consultant.profil_id][month] = 0
            nDays[consultant.profil_id][month] += Timesheet.objects.filter(consultant=consultant, working_date__gte=month, working_date__lt=upperBound, mission__nature="PROD").aggregate(Sum("charge"))["charge__sum"] or 0
            turnover[consultant.profil_id][month] += consultant.get_turnover(month, upperBound)

        for profil, profilName in profils.items():
            if profil in nDays:
                try:
                    avgDailyRate[profil][month] = round(turnover[profil][month] / nDays[profil][month])
                    monthGlobalNDays += nDays[profil][month]
                    monthGlobalTurnover += turnover[profil][month]
                except (KeyError, ZeroDivisionError):
                    avgDailyRate[profil][month] = None
        if monthGlobalNDays > 0 :
            globalDailyRate.append(round(monthGlobalTurnover / monthGlobalNDays))
        else:
            globalDailyRate.append(None)
        month = nextMonth(month)

    if not isoTimesheetMonths or set(globalDailyRate) == {None}:
        return HttpResponse('')

    graph_data.append(["x"] + isoTimesheetMonths)

    # Compute per profil
    for profil, profilName in profils.items():
        data = [profilName]
        month = timesheetStartDate
        while month < timesheetEndDate:
            data.append(avgDailyRate[profil][month])
            month = nextMonth(month)
        graph_data.append(data)

    graph_data.append([_("Global"), *globalDailyRate ])

    return render(request, "staffing/graph_profile_rates.html",
              {"graph_data": json.dumps(graph_data),
               "series_colors": COLORS,
               "user": request.user})


@pydici_non_public
@cache_page(60 * 60 * 4)
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

    if len(kdates) == 0:
        return HttpResponse("")

    # Avg daily rate / month and objective rate
    for refDate in kdates:
        next_month = nextMonth(refDate)
        prodRate = consultant.get_production_rate(refDate, next_month)
        if prodRate:
            prodRateData.append(round(100 * prodRate, 1))
            isoProdDates.append(refDate.isoformat())
        wdays = Timesheet.objects.filter(consultant=consultant, working_date__gte=refDate, working_date__lt=next_month, mission__nature="PROD").aggregate(Sum("charge"))["charge__sum"]
        if wdays:
            turnover = consultant.get_turnover(refDate, next_month)
            dailyRateData.append(int(turnover / wdays))
            isoRateDates.append(refDate.isoformat())
        rate = consultant.get_rate_objective(working_date=refDate, rate_type="DAILY_RATE")
        if rate and wdays:
            dailyRateObj.append(rate.rate)
        rate = consultant.get_rate_objective(working_date=refDate, rate_type="PROD_RATE")
        if rate and wdays:
            prodRateObj.append(rate.rate)

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
