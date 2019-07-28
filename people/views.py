# coding: utf-8
"""
Pydici people views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date

from django.shortcuts import render, redirect
from django.http import Http404

from people.models import Consultant
from people.learn import predict_similar, predict_similar_consultant
from crm.models import Company
from staffing.models import Holiday, Timesheet
from core.decorator import pydici_non_public
from core.utils import working_days, previousMonth, nextMonth
from people.forms import SimilarConsultantForm
from people.utils import compute_consultant_tasks


def _consultant_home(request, consultant):
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
        staff = consultant.team(onlyActive=True)
        month = date.today().replace(day=1)
        # Compute consultant current mission based on forecast
        missions = consultant.active_missions().filter(nature="PROD").filter(lead__state="WON")
        # Identify staled missions that may need new staffing or archiving
        staled_missions = [m for m in missions if m.no_more_staffing_since()]
        # Consultant clients and missions
        business_territory = Company.objects.filter(businessOwner=consultant)
        leads_as_responsible = set(consultant.lead_responsible.active())
        leads_as_staffee = consultant.lead_set.active()
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
        monthTurnover = consultant.getTurnover(month)
        lastMonthTurnover = None
        day = date.today().day
        while lastMonthTurnover is None:
            try:
                lastMonthTurnover = consultant.getTurnover(previousMonth(month), previousMonth(month).replace(day=day))  # Turnover for last month up to the same day
            except ValueError:
                # Corner case, last month has fewer days than current one. Go back one day and try again till it works.
                lastMonthTurnover = None
                day -= 1
        if lastMonthTurnover:
            turnoverVariation = 100 * (monthTurnover - lastMonthTurnover) / lastMonthTurnover
        else:
            turnoverVariation = 100
        # Daily rate
        fc = consultant.getFinancialConditions(month, nextMonth(month))
        if fc:
            daily_rate = int(sum([rate * days for rate, days in fc]) / sum([days for rate, days in fc]))
        else:
            daily_rate = 0
        daily_rate_objective = consultant.getRateObjective(workingDate=month, rate_type="DAILY_RATE")
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
        prod_rate = round(100 * consultant.getProductionRate(month, nextMonth(month)), 1)
        prod_rate_objective = consultant.getRateObjective(workingDate=month, rate_type="PROD_RATE")
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
                   "business_territory": business_territory,
                   "leads_as_responsible": leads_as_responsible,
                   "leads_as_staffee": leads_as_staffee,
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
                   "tasks": compute_consultant_tasks(consultant),
                   "user": request.user})


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
def similar_consultant(request):
    """This page allows to find a consultant by its experience or similar to another"""
    result = []
    if request.method == "POST":
        form = SimilarConsultantForm(request.POST)
        if form.is_valid():
            consultant = form.cleaned_data["consultant"]
            tags = form.cleaned_data["tags"]
            daily_rate = form.cleaned_data["daily_rate"]
            experience = form.cleaned_data["experience"]
            if consultant:
                result = predict_similar_consultant(form.cleaned_data["consultant"])
            if tags:
                features = {tag.name: 1 for tag in tags}
                features["avg_daily_rate"] = float(daily_rate)
                features["experience"] = float(experience)
                result = predict_similar(features)
                # Clean form in case user submited both consultant and tags
                form = SimilarConsultantForm(initial={"tags": tags, "daily_rate": daily_rate, "experience": experience})

    else:
        form = SimilarConsultantForm() # An unbound form

    return render(request, "people/similar_consultant.html",
                  {"form": form,
                   "result": result,
                   "user": request.user})
