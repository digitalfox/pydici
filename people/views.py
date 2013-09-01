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
from crm.models import Company
from staffing.models import Holiday
from core.decorator import pydici_non_public
from core.utils import working_days, previousMonth


def consultant_home(request, consultant_id):
    """Home page of consultant - this page loads all others mission sub-pages"""
    return render(request, 'people/consultant.html',
                  {"consultant": Consultant.objects.get(id=consultant_id),
                   "user": request.user})


@pydici_non_public
def consultant_detail(request, consultant_id):
    """Summary page of consultant activity"""
    if not request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        # This view should only be accessed by ajax request. Redirect lost users
        return redirect(consultant_home, consultant_id)
    try:
        consultant = Consultant.objects.get(id=consultant_id)
        staff = consultant.team(onlyActive=True)
        month = date.today().replace(day=1)
        # Compute user current mission based on forecast
        missions = consultant.active_missions().filter(nature="PROD").filter(probability=100)
        companies = Company.objects.filter(clientorganisation__client__lead__mission__timesheet__consultant=consultant).distinct()
        business_territory = Company.objects.filter(businessOwner=consultant)
        leads_as_responsible = set(consultant.lead_responsible.active())
        leads_as_staffee = consultant.lead_set.active()
        first_day = date.today().replace(day=1)
        holidays = [h.day for h in Holiday.objects.all()]
        month_days = working_days(first_day, holidays, upToToday=False)
        done_days = consultant.done_days()
        late = working_days(first_day, holidays, upToToday=True) - done_days
        if late < 0:
            late = 0  # Don't warn user if timesheet is ok !
        to_be_done = month_days - late - done_days
        forecasting_balance = month_days - consultant.forecasted_days()
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
    except Consultant.DoesNotExist:
        raise Http404
    return render(request, "people/consultant_detail.html",
                  {"consultant": consultant,
                   "staff": staff,
                   "missions": missions,
                   "companies": companies,
                   "business_territory": business_territory,
                   "leads_as_responsible": leads_as_responsible,
                   "leads_as_staffee": leads_as_staffee,
                   "done_days": done_days,
                   "late": late,
                   "to_be_done": to_be_done,
                   "month_days": month_days,
                   "forecasting_balance": forecasting_balance,
                   "month_turnover": monthTurnover,
                   "turnover_variation": turnoverVariation,
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
