# coding: utf-8
"""
Pydici people views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta
import json

from django.shortcuts import render, redirect
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.views.decorators.cache import cache_page
from django.utils.translation import gettext as _
from django.db.models import Count

from people.models import Consultant
from crm.models import Company
from crm.utils import get_subsidiary_from_session
from staffing.models import Holiday
from core.decorator import pydici_non_public, pydici_subcontractor
from core.utils import working_days, previousMonth, nextMonth, COLORS, user_has_feature
from people.utils import subcontractor_is_user
from crm.models import Subsidiary


def _consultant_home(request, consultant):
    if not subcontractor_is_user(consultant, request.user):
        # subcontractor cannot see other people page
        return HttpResponseRedirect(reverse("core:forbidden"))

    return render(request, 'people/consultant.html',
                  {"consultant": consultant,
                   "user": request.user})


def consultant_home_by_id(request, consultant_id):
    """Home page of consultant - this page loads all others mission sub-pages"""
    return _consultant_home(request, Consultant.objects.get(id=consultant_id))


def consultant_home(request, consultant_trigramme):
    """Home page of consultant - this page loads all others mission sub-pages"""
    return _consultant_home(request, Consultant.objects.get(trigramme__iexact=consultant_trigramme))


@pydici_non_public
def consultant_detail(request, consultant_id):
    """Summary page of consultant activity"""
    if not request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        # This view should only be accessed by ajax request. Redirect lost users
        return redirect("people:consultant_home_by_id", consultant_id)
    try:
        consultant = Consultant.objects.get(id=consultant_id)
        staff = consultant.team(only_active=True)
        month = date.today().replace(day=1)
        # Compute consultant current production mission based on forecast and responsibility
        missions = consultant.current_missions().filter(nature="PROD")
        # Identify staled missions that may need new staffing or archiving
        staled_missions = [m for m in missions if m.no_more_staffing_since()]
        # Timesheet donut data
        holidays = [h.day for h in Holiday.objects.all()]
        month_days = working_days(month, holidays, upToToday=False)
        done_days = consultant.done_days()
        late = working_days(month, holidays, upToToday=True) - done_days
        if late < 0:
            late = 0  # Don't warn user if timesheet is ok !
        # Forecast donut data
        forecasted = consultant.forecasted_days()
        to_be_done = month_days - late - done_days
        forecasting_balance = month_days - forecasted
        if forecasting_balance < 0:
            overhead = -forecasting_balance
            missing = 0
        else:
            overhead = 0
            missing = forecasting_balance
        # Turnover
        monthTurnover = consultant.get_turnover(month)
        lastMonthTurnover = None
        day = date.today().day
        while lastMonthTurnover is None:
            try:
                lastMonthTurnover = consultant.get_turnover(previousMonth(month), previousMonth(month).replace(day=day))  # Turnover for last month up to the same day
            except ValueError:
                # Corner case, last month has fewer days than current one. Go back one day and try again till it works.
                lastMonthTurnover = None
                day -= 1
        if lastMonthTurnover:
            turnoverVariation = 100 * (monthTurnover - lastMonthTurnover) / lastMonthTurnover
        else:
            turnoverVariation = 100
        # Daily rate
        fc = consultant.get_financial_conditions(month, nextMonth(month))
        if fc:
            daily_rate = int(sum([rate * days for rate, days in fc]) / sum([days for rate, days in fc]))
        else:
            daily_rate = 0
        daily_rate_objective = consultant.get_rate_objective(working_date=month, rate_type="DAILY_RATE")
        if daily_rate_objective:
            daily_rate_objective = daily_rate_objective.rate
        else:
            daily_rate_objective = daily_rate
        if daily_rate > daily_rate_objective:
            daily_overhead = daily_rate - daily_rate_objective
            daily_missing = 0
            daily_rate -= daily_overhead
        else:
            daily_overhead = 0
            daily_missing = daily_rate_objective - daily_rate
        # Production rate
        prod_rate = round(100 * consultant.get_production_rate(month, nextMonth(month)), 1)
        prod_rate_objective = consultant.get_rate_objective(working_date=month, rate_type="PROD_RATE")
        if prod_rate_objective:
            prod_rate_objective = prod_rate_objective.rate
        else:
            prod_rate_objective = prod_rate
        if prod_rate > prod_rate_objective:
            prod_overhead = round(prod_rate - prod_rate_objective, 1)
            prod_missing = 0
            prod_rate -= prod_overhead
        else:
            prod_overhead = 0
            prod_missing = round(prod_rate_objective - prod_rate, 1)
    except Consultant.DoesNotExist:
        raise Http404
    return render(request, "people/consultant_detail.html",
                  {"consultant": consultant,
                   "staff": staff,
                   "missions": missions,
                   "staled_missions": staled_missions,
                   "business_territory": Company.objects.filter(businessOwner=consultant),
                   "leads_as_responsible": consultant.active_leads(),
                   "leads_as_staffee": consultant.lead_set.active(),
                   "done_days": done_days,
                   "late": late,
                   "to_be_done": to_be_done,
                   "forecasted": forecasted,
                   "missing": missing,
                   "overhead": overhead,
                   "prod_rate": prod_rate,
                   "prod_overhead": prod_overhead,
                   "prod_missing": prod_missing,
                   "daily_rate": daily_rate,
                   "daily_overhead": daily_overhead,
                   "daily_missing": daily_missing,
                   "month_days": month_days,
                   "forecasting_balance": forecasting_balance,
                   "month_turnover": monthTurnover,
                   "turnover_variation": turnoverVariation,
                   "user": request.user})


@pydici_subcontractor
def subcontractor_detail(request, consultant_id):
    """This is the subcontractor home page"""
    try:
        consultant = Consultant.objects.get(id=consultant_id)
        missions = consultant.active_missions().filter(nature="PROD").filter(probability=100)
        companies = Company.objects.filter(clientorganisation__client__lead__mission__timesheet__consultant=consultant).distinct()
        leads_as_staffee = consultant.lead_set.active()
    except Consultant.DoesNotExist:
        raise Http404
    if not consultant.subcontractor:
        raise Http404
    return render(request, "people/subcontractor_detail.html",
                  {"consultant": consultant,
                   "missions": missions,
                   "companies": companies,
                   "leads_as_staffee": leads_as_staffee,
                   "user": request.user})

@pydici_non_public
def consultants_tasks(request):
    """display all active consultants tasks"""
    consultants = Consultant.objects.filter(active=True, subcontractor=False)
    subsidiary = get_subsidiary_from_session(request)
    if subsidiary:
        consultants = consultants.filter(company=subsidiary)
    return render(request, "people/consultants_tasks.html",
                  {"consultants": consultants})

@pydici_non_public
@cache_page(60 * 60 * 24)
def graph_people_count(request):
    """Active people count"""
    #TODO: add start/end timeframe
    graph_data = []
    iso_months = []
    start_date = (date.today() - 3 * timedelta(365)).replace(day=1)  # Last three years
    end_date = date.today().replace(day=1)
    consultants_count = {}
    subcontractors_count = {}

    consultants = Consultant.objects.filter(subcontractor=False, productive=True)
    subcontractors = Consultant.objects.filter(subcontractor=True, productive=True)

    subsidiary = get_subsidiary_from_session(request)
    if subsidiary:
        subsidiaries = [subsidiary,]
        consultants = consultants.filter(company=subsidiary)
        subcontractors = subcontractors.filter(timesheet__mission__subsidiary=subsidiary)
    else:
        subsidiaries = Subsidiary.objects.filter(mission__nature="PROD").distinct()
        subsidiaries = subsidiaries.annotate(Count("mission__timesheet__consultant"))
        subsidiaries = subsidiaries.filter(mission__timesheet__consultant__count__gt=0)

    for subsidiary in subsidiaries:
        consultants_count[subsidiary] = []
        subcontractors_count[subsidiary] = []

    month = start_date
    while month < end_date:
        next_month = nextMonth(month)
        iso_months.append(month.isoformat())
        for subsidiary in subsidiaries:
            consultants_count[subsidiary].append(consultants.filter(company=subsidiary,
                                                                    timesheet__mission__nature__in=("PROD", "NONPROD"),
                                                                    timesheet__working_date__gte=month,
                                                                    timesheet__working_date__lt=next_month).distinct().count())
            subcontractors_count[subsidiary].append(subcontractors.filter(timesheet__working_date__gte=month,
                                                                          timesheet__working_date__lt=next_month,
                                                                          timesheet__mission__subsidiary=subsidiary,
                                                                          timesheet__mission__nature="PROD").distinct().count())

        month = next_month

    if not iso_months or set(consultants_count) == {None}:
        return HttpResponse('')

    graph_data.append(["x"] + iso_months)
    for subsidiary in subsidiaries:
        graph_data.append([_("consultants %s" % subsidiary)] + consultants_count[subsidiary])
        graph_data.append([_("subcontractors %s" % subsidiary)] + subcontractors_count[subsidiary])

    return render(request, "people/graph_people_count.html",
              {"graph_data": json.dumps(graph_data),
               "series_colors": COLORS,
               "subsidiaries": subsidiaries,
               "user": request.user})
