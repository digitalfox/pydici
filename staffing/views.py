# coding: utf-8
"""
Pydici staffing views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from datetime import date, timedelta
import csv
import itertools

from matplotlib.figure import Figure

from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.contrib.auth.decorators import permission_required
from django.forms.models import inlineformset_factory
from django.utils.translation import ugettext as _
from django.core import urlresolvers
from django.template import RequestContext
from django.db.models import Sum
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.utils import formats
from django.views.decorators.cache import cache_page, cache_control


from pydici.staffing.models import Staffing, Mission, Holiday, Timesheet, FinancialCondition, LunchTicket
from pydici.people.models import Consultant
from pydici.leads.models import Lead
from pydici.people.models import ConsultantProfile
from pydici.staffing.forms import ConsultantStaffingInlineFormset, MissionStaffingInlineFormset, TimesheetForm
from pydici.core.utils import working_days, to_int_or_round, print_png, COLORS
from pydici.staffing.utils import gatherTimesheetData, saveTimesheetData, saveFormsetAndLog, \
                                  sortMissions, holidayDays, daysOfMonth, staffingDates, \
                                  previousWeek, nextWeek, monthWeekNumber

def missions(request, onlyActive=True):
    """List of missions"""
    if onlyActive:
        missions = Mission.objects.filter(active=True)
        all = False
    else:
        missions = Mission.objects.all()
        all = True
    return render_to_response("staffing/missions.html",
                              {"missions": missions,
                               "all": all,
                               "user": request.user },
                               RequestContext(request))

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def mission_staffing(request, mission_id):
    """Edit mission staffing"""
    if (request.user.has_perm("staffing.add_staffing") and
        request.user.has_perm("staffing.change_staffing") and
        request.user.has_perm("staffing.delete_staffing")):
        readOnly = False
    else:
        readOnly = True

    StaffingFormSet = inlineformset_factory(Mission, Staffing,
                                            formset=MissionStaffingInlineFormset)
    mission = Mission.objects.get(id=mission_id)
    if request.method == "POST":
        if readOnly:
            # Readonly users should never go here !
            return HttpResponseRedirect(urlresolvers.reverse("forbiden"))
        formset = StaffingFormSet(request.POST, instance=mission)
        if formset.is_valid():
            saveFormsetAndLog(formset, request)
            formset = StaffingFormSet(instance=mission) # Recreate a new form for next update
    else:
        formset = StaffingFormSet(instance=mission) # An unbound form 

    return render_to_response('staffing/mission_staffing.html',
                              {"formset": formset,
                               "mission": mission,
                               "link_to_staffing" : True, # for mission_base template links
                               "consultant_rates": mission.consultant_rates(),
                               "read_only" : readOnly,
                               "staffing_dates" : staffingDates(),
                               "user": request.user},
                               RequestContext(request))


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
                                          formset=ConsultantStaffingInlineFormset)

    if request.method == "POST":
        formset = StaffingFormSet(request.POST, instance=consultant)
        if formset.is_valid():
            saveFormsetAndLog(formset, request)
            formset = StaffingFormSet(instance=consultant) # Recreate a new form for next update
    else:
        formset = StaffingFormSet(instance=consultant) # An unbound form

    missions = consultant.active_missions()
    missions = sortMissions(missions)

    return render_to_response('staffing/consultant_staffing.html',
                              {"formset": formset,
                               "consultant": consultant,
                               "missions": missions,
                               "link_to_staffing" : True, # for consultant_base template links
                               "staffing_dates" : staffingDates(),
                               "user": request.user },
                               RequestContext(request))


def pdc_review(request, year=None, month=None):
    """PDC overview
    @param year: start date year. None means current year
    @param year: start date year. None means current month"""

    #TODO: factorise this code in a decorator
    mobile = request.session.get("mobile", False)

    # Don't display this page if no productive consultant are defined
    if Consultant.objects.filter(productive=True).filter(active=True).count() == 0:
        #TODO: make this message nice
        return HttpResponse(_("No productive consultant defined !"))

    if mobile:
        n_month = 1
    else:
        n_month = 3

    if "n_month" in request.GET:
        try:
            n_month = int(request.GET["n_month"])
            if n_month > 12:
                n_month = 12 # Limit to 12 month to avoid complex and useless month list computation
        except ValueError:
            pass

    if "projected" in request.GET:
        projected = True
    else:
        projected = False

    groupby = "manager"
    if "groupby" in request.GET:
        if request.GET["groupby"] in ("manager", "position"):
            groupby = request.GET["groupby"]

    if year and month:
        start_date = date(int(year), int(month), 1)
    else:
        start_date = date.today()
        start_date = start_date.replace(day=1) # We use the first day to represent month

    staffing = {} # staffing data per month and per consultant
    total = {}    # total staffing data per month
    rates = []     # staffing rates per month
    available_month = {} # available working days per month
    months = []   # list of month to be displayed
    people = Consultant.objects.filter(productive=True).filter(active=True).count()

    for i in range(n_month):
        if start_date.month + i <= 12:
            months.append(start_date.replace(month=start_date.month + i))
        else:
            # We wrap around a year (max one year)
            months.append(start_date.replace(month=start_date.month + i - 12, year=start_date.year + 1))

    previous_slice_date = start_date - timedelta(days=(28 * n_month))
    next_slice_date = start_date + timedelta(days=(31 * n_month))

    # Initialize total dict and available dict
    holidays_days = [h.day for h in Holiday.objects.all()]
    for month in months:
        total[month] = {"prod":0, "unprod":0, "holidays":0, "available":0}
        available_month[month] = working_days(month, holidays_days)

    # Get consultants staffing
    for consultant in Consultant.objects.select_related().filter(productive=True).filter(active=True):
        staffing[consultant] = []
        missions = set()
        for month in months:
            if projected:
                # Only exclude null (0%) mission
                current_staffings = consultant.staffing_set.filter(staffing_date=month, mission__probability__gt=0).order_by()
            else:
                # Only keep 100% mission
                current_staffings = consultant.staffing_set.filter(staffing_date=month, mission__probability=100).order_by()

            # Sum staffing
            prod = []
            unprod = []
            holidays = []
            for current_staffing  in current_staffings:
                nature = current_staffing.mission.nature
                if nature == "PROD":
                    missions.add(current_staffing.mission) # Store prod missions for this consultant
                    prod.append(current_staffing.charge * current_staffing.mission.probability / 100)
                elif nature == "NONPROD":
                    unprod.append(current_staffing.charge * current_staffing.mission.probability / 100)
                elif nature == "HOLIDAYS":
                    holidays.append(current_staffing.charge * current_staffing.mission.probability / 100)

            # Staffing computation
            prod = to_int_or_round(sum(prod))
            unprod = to_int_or_round(sum(unprod))
            holidays = to_int_or_round(sum(holidays))
            available = available_month[month] - (prod + unprod + holidays)
            staffing[consultant].append([prod, unprod, holidays, available])
            total[month]["prod"] += prod
            total[month]["unprod"] += unprod
            total[month]["holidays"] += holidays
            total[month]["available"] += available
        # Add client synthesis to staffing dict
        if not mobile:
            company = set([m.lead.client.organisation.company for m in list(missions)])
            staffing[consultant].append([", ".join(["<a href='%s'>%s</a>" %
                                                    (urlresolvers.reverse("pydici.crm.views.company_detail", args=[c.id]),
                                                     unicode(c)) for c in company])])

    # Compute indicator rates
    for month in months:
        rate = []
        ndays = people * available_month[month] # Total days for this month
        for indicator in ("prod", "unprod", "holidays", "available"):
            if indicator == "holidays":
                rate.append(100.0 * total[month][indicator] / ndays)
            else:
                rate.append(100.0 * total[month][indicator] / (ndays - total[month]["holidays"]))
        rates.append(map(to_int_or_round, rate))

    # Format total dict into list
    total = total.items()
    total.sort(cmp=lambda x, y:cmp(x[0], y[0])) # Sort according date
    # Remove date, and transform dict into ordered list:
    total = [(to_int_or_round(i[1]["prod"]),
            to_int_or_round(i[1]["unprod"]),
            to_int_or_round(i[1]["holidays"]),
            to_int_or_round(i[1]["available"])) for i in total]

    # Order staffing list
    staffing = staffing.items()
    staffing.sort(cmp=lambda x, y:cmp(x[0].name, y[0].name)) # Sort by name
    if groupby == "manager":
        staffing.sort(cmp=lambda x, y:cmp(unicode(x[0].manager), unicode(y[0].manager))) # Sort by manager
    else:
        staffing.sort(cmp=lambda x, y:cmp(x[0].profil.level, y[0].profil.level)) # Sort by position

    return render_to_response("staffing/pdc_review.html",
                              {"staffing": staffing,
                               "months": months,
                               "total": total,
                               "rates": rates,
                               "user": request.user,
                               "projected": projected,
                               "previous_slice_date" : previous_slice_date,
                               "next_slice_date" : next_slice_date,
                               "start_date" : start_date,
                               "groupby" : groupby},
                               RequestContext(request))

def deactivate_mission(request, mission_id):
    """Deactivate the given mission"""
    mission = Mission.objects.get(id=mission_id)
    mission.active = False
    mission.save()
    return HttpResponseRedirect(urlresolvers.reverse("missions"))


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def consultant_timesheet(request, consultant_id, year=None, month=None, week=None):
    """Consultant timesheet"""

    mobile = request.session.get("mobile", False)

    # We use the first day to represent month
    if year and month:
        month = date(int(year), int(month), 1)
    else:
        month = date.today().replace(day=1)

    if week:
        week = int(week)
    elif mobile:
        # Force week display
        week = monthWeekNumber(date.today())

    forecastTotal = {} # forecast charge (value) per mission (key is mission.id)
    missions = set()   # Set of all consultant missions for this month    
    days = daysOfMonth(month, week=week) # List of days in month

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

    consultant = Consultant.objects.get(id=consultant_id)
    readOnly = False # Wether timesheet is readonly or not

    if not (request.user.has_perm("staffing.add_timesheet") and
            request.user.has_perm("staffing.change_timesheet") and
            request.user.has_perm("staffing.delete_timesheet")):
        # Only forbid access if the user try to edit someone else staffing
        if request.user.username.upper() != consultant.trigramme:
            return HttpResponseRedirect(urlresolvers.reverse("forbiden"))

        # A consultant can only edit his own timesheet on current month and 5 days after
        if (date.today() - next_date).days > 5:
            readOnly = True


    staffings = Staffing.objects.filter(consultant=consultant)
    staffings = staffings.filter(staffing_date__gte=days[0]).filter(staffing_date__lte=days[-1])
    for staffing in staffings:
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

    if request.method == 'POST': # If the form has been submitted...
        if readOnly:
            # We should never go here as validate button is not displayed when read only...
            # This is just a security control
            return HttpResponseRedirect(urlresolvers.reverse("forbiden"))
        form = TimesheetForm(request.POST, days=days, missions=missions, holiday_days=holiday_days,
                             forecastTotal=forecastTotal, timesheetTotal=timesheetTotal)
        if form.is_valid(): # All validation rules pass
            # Process the data in form.cleaned_data
            saveTimesheetData(consultant, month, form.cleaned_data, timesheetData)
            # Recreate a new form for next update and compute again totals
            timesheetData, timesheetTotal, warning = gatherTimesheetData(consultant, missions, month)
            form = TimesheetForm(days=days, missions=missions, holiday_days=holiday_days,
                                 forecastTotal=forecastTotal, timesheetTotal=timesheetTotal, initial=timesheetData)
    else:
        # An unbound form
        form = TimesheetForm(days=days, missions=missions, holiday_days=holiday_days,
                             forecastTotal=forecastTotal, timesheetTotal=timesheetTotal, initial=timesheetData)

    # Compute workings days of this month and compare it to declared days
    wDays = working_days(month, holiday_days)
    wDaysBalance = wDays - (sum(timesheetTotal.values()) - timesheetTotal["ticket"])

    # Shrink warning list to given week if week number is given
    if week:
        warning = warning[days[0].day - 1:days[-1].day]

    return render_to_response("staffing/consultant_timesheet.html", {
                                "consultant": consultant,
                               "form": form,
                               "read_only" : readOnly,
                               "days": days,
                               "month": month,
                               "week" : week,
                               "missions": missions,
                               "working_days_balance" : wDaysBalance,
                               "working_days" : wDays,
                               "warning": warning,
                               "next_date": next_date,
                               "previous_date": previous_date,
                               "previous_week" : previous_week,
                               "next_week" : next_week,
                               "link_to_staffing" : False, # for consultant_base template links
                               "user": request.user },
                               RequestContext(request))


def consultant_csv_timesheet(request, consultant, days, month, missions):
    """@return: csv timesheet for a given consultant"""
    response = HttpResponse(mimetype="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s" % _("timesheet.csv")
    writer = csv.writer(response, delimiter=';')

    # Header
    writer.writerow([("%s - %s" % (unicode(consultant), month)).encode("ISO-8859-15"), ])

    # Days
    writer.writerow(["", ""] + [d.day for d in days])
    writer.writerow([_("Mission").encode("ISO-8859-15", "ignore"), _("Deal id").encode("ISO-8859-15", "ignore")]
                     + [_(d.strftime("%a")) for d in days] + [_("total")])

    for mission in missions:
        total = 0
        row = [i.encode("ISO-8859-15", "ignore") for i in [unicode(mission), mission.mission_id()]]
        timesheets = Timesheet.objects.select_related().filter(consultant=consultant).filter(mission=mission)
        for day in days:
            try:
                timesheet = timesheets.get(working_date=day)
                row.append(formats.number_format(timesheet.charge))
                total += timesheet.charge
            except Timesheet.DoesNotExist:
                row.append("")
        row.append(formats.number_format(total))
        writer.writerow(row)

    return response

def mission_timesheet(request, mission_id):
    """Mission timesheet"""
    mission = Mission.objects.get(id=mission_id)
    current_month = date.today().replace(day=1) # Current month
    next_month = (current_month + timedelta(days=40)).replace(day=1)
    consultants = mission.staffed_consultant()
    consultant_rates = mission.consultant_rates()

    # Gather timesheet (Only consider timesheet up to current month)
    timesheets = Timesheet.objects.filter(mission=mission).filter(working_date__lt=next_month).order_by("working_date")
    timesheetMonths = list(timesheets.dates("working_date", "month"))

    # Gather forecaster (till current month)
    staffings = Staffing.objects.filter(mission=mission).filter(staffing_date__gte=current_month).order_by("staffing_date")
    staffingMonths = list(staffings.dates("staffing_date", "month"))

    missionData = [] # list of tuple (consultant, (charge month 1, charge month 2), (forecast month 1, forcast month2)
    for consultant in consultants:
        # Timesheet data
        timesheetData = []
        for month in timesheetMonths:
            timesheetData.append(sum([t.charge for t in timesheets.filter(consultant=consultant) if t.working_date.month == month.month]))
        timesheetData.append(sum(timesheetData)) # Add total per consultant
        timesheetData.append(timesheetData[-1] * consultant_rates[consultant] / 1000) # Add total in money

        # Forecast staffing data
        staffingData = []
        for month in staffingMonths:
            data = sum([t.charge for t in staffings.filter(consultant=consultant) if t.staffing_date.month == month.month])
            if timesheetMonths  and \
               date(timesheetMonths[-1].year, timesheetMonths[-1].month, 1) == current_month and \
               date(month.year, month.month, 1) == current_month:
                # Remove timesheet days from current month forecast days
                data -= timesheetData[-3] # Last is total in money, the one before is total in days
            staffingData.append(data)
        staffingData.append(sum(staffingData)) # Add total per consultant
        staffingData.append(staffingData[-1] * consultant_rates[consultant] / 1000) # Add total in money
        missionData.append((consultant, timesheetData, staffingData))

    # Compute total per month
    timesheetTotal = [timesheet for consultant, timesheet, staffing in missionData]
    timesheetTotal = zip(*timesheetTotal) # [ [1, 2, 3], [4, 5, 6]... ] => [ [1, 4], [2, 5], [4, 6]...]
    timesheetTotal = [sum(t) for t in timesheetTotal]
    staffingTotal = [staffing for consultant, timesheet, staffing in missionData]
    staffingTotal = zip(*staffingTotal) # [ [1, 2, 3], [4, 5, 6]... ] => [ [1, 4], [2, 5], [4, 6]...]
    staffingTotal = [sum(t) for t in staffingTotal]
    if mission.price and timesheetTotal and staffingTotal:
        margin = float(mission.price) - timesheetTotal[-1] - staffingTotal[-1]
        margin = to_int_or_round(margin, 3)
    else:
        margin = 0
    missionData.append((None, timesheetTotal, staffingTotal))

    missionData = map(to_int_or_round, missionData)

    return render_to_response("staffing/mission_timesheet.html", {
                                "mission": mission,
                                "margin": margin,
                                "timesheet_months": timesheetMonths,
                                "staffing_months": staffingMonths,
                                "mission_data": missionData,
                                "consultant_rates" : consultant_rates,
                                "link_to_staffing" : False, # for mission_base template links
                               "user": request.user },
                               RequestContext(request))


def all_timesheet(request, year=None, month=None):
    if year and month:
        month = date(int(year), int(month), 1)
    else:
        month = date.today().replace(day=1) # We use the first day to represent month

    previous_date = (month - timedelta(days=5)).replace(day=1)
    next_date = (month + timedelta(days=40)).replace(day=1)

    timesheets = Timesheet.objects.filter(working_date__gte=month) # Filter on current month
    timesheets = timesheets.filter(working_date__lt=next_date.replace(day=1)) # Discard next month
    timesheets = timesheets.values("consultant", "mission") # group by consultant, mission
    timesheets = timesheets.annotate(sum=Sum('charge')).order_by("mission", "consultant") # Sum and clean order by (else, group by won't work because of default ordering)
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
        data = [mark_safe("<a href='%s'>%s</a>" % (urlresolvers.reverse("pydici.staffing.views.consultant_timesheet", args=[consultant.id, month.year, month.month]),
                                        escape(unicode(consultant)))) for consultant in consultants]
    data = [[_("Mission"), _("Deal id")] + data]
    for timesheet in timesheets:
        charges[(timesheet["mission"], timesheet["consultant"])] = timesheet["sum"]
    for mission in missions:
        missionUrl = "<a href='%s'>%s</a>" % (urlresolvers.reverse("pydici.staffing.views.mission_timesheet", args=[mission.id, ]),
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
        total = zip(*total) # [ [1, 2, 3], [4, 5, 6]... ] => [ [1, 4], [2, 5], [4, 6]...]
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
        return render_to_response("staffing/all_timesheet.html", {
                               "user": request.user,
                               "next_date": next_date,
                               "previous_date": previous_date,
                               "month" : month,
                               "consultants" : consultants,
                               "missions" : missions,
                               "charges" : charges },
                               RequestContext(request))


def all_csv_timesheet(request, charges, month):
    response = HttpResponse(mimetype="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s" % _("timesheet.csv")
    writer = csv.writer(response, delimiter=';')

    # Header
    writer.writerow([unicode(month).encode("ISO-8859-15"), ])
    for charge in charges:
        row = []
        for i in charge:
            if isinstance(i, float):
                i = formats.number_format(i)
            else:
                i = unicode(i).encode("ISO-8859-15", "ignore")
            row.append(i)
        writer.writerow(row)
    return response


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
    mission.nature = modelMission.nature
    mission.probability = modelMission.probability
    mission.save()
    mission.create_default_staffing() # Initialize default staffing

    # Redirect user to change page of the mission 
    # in order to type description and deal id
    return HttpResponseRedirect(urlresolvers.reverse("admin:staffing_mission_change", args=[mission.id, ]))

def mission_consultant_rate(request, mission_id, consultant_id):
    """Select or create financial condition for this consultant/mission tuple and redirect to admin change page"""
    mission = Mission.objects.get(id=mission_id)
    consultant = Consultant.objects.get(id=consultant_id)
    condition, created = FinancialCondition.objects.get_or_create(mission=mission, consultant=consultant,
                                                                  defaults={"daily_rate":0})
    return HttpResponseRedirect(urlresolvers.reverse("admin:staffing_financialcondition_change", args=[condition.id, ]))


@cache_page(60 * 10)
def graph_timesheet_rates_bar(request):
    """Nice graph bar of timesheet prod/holidays/nonprod rates
    @todo: per year, with start-end date"""
    data = {} # Graph data
    natures = [i[0] for i in Mission.MISSION_NATURE] # Mission natures
    kdates = set() # List of uniq month
    nConsultant = {} # Set of working consultant id per month
    avgDailyRate = {} # daily rate sum per month
    nDays = {} # number of days with valid rate per month
    plots = [] # List of plots for prod rate - needed to add legend
    plots2 = [] # List of plots for daily rate - needed to add legend
    colors = itertools.cycle(COLORS)
    holiday_days = [h.day for h in  Holiday.objects.all()]
    profils = dict(ConsultantProfile.objects.all().values_list("id", "name")) # Consultant Profiles

    # Setting up graph
    fig = Figure(figsize=(12, 8))
    fig.set_facecolor("white")
    ax = fig.add_subplot(211) # Main graph for prod rate and days
    ax2 = fig.add_subplot(212, sharex=ax) # Second graph for avg daily rate
    fig.subplots_adjust(hspace=0.3)

    # Create dict per mission nature
    for nature in natures:
        data[nature] = {}

    # Create dict per consultant profile
    for profilId in profils.keys():
        avgDailyRate[profilId] = {}
        nDays[profilId] = {}

    # Gather data
    timesheets = Timesheet.objects.select_related().all()
    if timesheets.count() == 0:
        return print_png(fig)

    for timesheet in timesheets:
        #Using first day of each month as key date
        kdate = date(timesheet.working_date.year, timesheet.working_date.month, 1)
        kdates.add(kdate)
        # Init dict with kdate if not already done
        if not kdate in nConsultant:
            nConsultant[kdate] = set()
        if not kdate in avgDailyRate[timesheet.consultant.profil.id]:
            avgDailyRate[timesheet.consultant.profil.id][kdate] = 0
        if not kdate in nDays[timesheet.consultant.profil.id]:
            nDays[timesheet.consultant.profil.id][kdate] = 0
        # Gather data
        if kdate in data[timesheet.mission.nature]:
            data[timesheet.mission.nature][kdate] += timesheet.charge
        else:
            data[timesheet.mission.nature][kdate] = timesheet.charge
        nConsultant[kdate].add(timesheet.consultant.id)
        try:
            fc = FinancialCondition.objects.get(mission=timesheet.mission, consultant=timesheet.consultant)
            if fc.daily_rate > 0:
                avgDailyRate[timesheet.consultant.profil.id][kdate] += timesheet.charge * fc.daily_rate
                nDays[timesheet.consultant.profil.id][kdate] += timesheet.charge
        except FinancialCondition.DoesNotExist:
            pass

    # Set bottom of each graph. Starts if [0, 0, 0, ...]
    bottom = [0] * len(kdates)

    # Draw a bar for each nature
    kdates = list(kdates)
    kdates.sort() # Convert kdates to list and sort it
    for nature in natures:
        ydata = []
        for kdate in kdates:
            if data[nature].has_key(kdate):
                ydata.append(100 * data[nature][kdate] / (working_days(kdate, holiday_days) * len(nConsultant[kdate])))
            else:
                ydata.append(0)

        b = ax.bar(kdates, ydata, bottom=bottom, align="center", width=15,
                   color=colors.next())
        plots.append(b[0])
        for i in range(len(ydata)):
            bottom[i] += ydata[i] # Update bottom

    ydata = []  # Prod rate 
    y2data = {} # Average daily rate per profil

    for profilId in profils.keys():
        y2data[profilId] = []

    for kdate in kdates:
        # Days repart per type
        try:
            if kdate in data["NONPROD"]:
                ydata.append(100 * data["PROD"][kdate] / (data["PROD"][kdate] + data["NONPROD"][kdate]))
            else:
                ydata.append(100)
        except KeyError:
            ydata.append(0)
        ax.text(kdate, ydata[-1] + 4, "%.1f" % ydata[-1])

        # Rate per profil
        for profilId in profils.keys():
            if kdate in avgDailyRate[profilId] and kdate in nDays[profilId] and nDays[profilId][kdate] > 0:
                y2data[profilId].append(avgDailyRate[profilId][kdate] / nDays[profilId][kdate])
                ax2.text(kdate, y2data[profilId][-1] + 50, "%.1f" % y2data[profilId][-1])
            else:
                y2data[profilId].append(0)

    b = ax.plot(kdates, ydata, '--o', ms=10, lw=2, alpha=0.7, color="green", mfc="green")
    plots.append(b[0])
    for profilId in profils.keys():
        if sum(y2data[profilId]) != 0:
            color = colors.next()
            b = ax2.plot(kdates, y2data[profilId], '-o', ms=10, lw=4, color=color, mfc=color, label="profil-%s" % profilId)
            plots2.append(b[0])

    # Add Legend and setup axes
    ax.set_ylim(ymax=115)
    ax.set_xticks(kdates)
    ax.set_xticklabels([d.strftime("%b %y") for d in kdates])
    ax.set_ylabel("%")
    ax.legend(plots, [i[1] for i in Mission.MISSION_NATURE] + [_("Prod. rate")],
              bbox_to_anchor=(0., 1.02, 1., .102), loc=4,
              ncol=4, borderaxespad=0.)
    ax.grid(True)

    if len([i for i in sum(y2data.values(), []) if i > 0]) == 0:
        # Second graph (ax2) is empty
        return print_png(fig)

    # ymin is set as the min non null rate minus 200. Sum is used to flatten list of list
    ax2.set_ylim(ymin=min([i for i in sum(y2data.values(), []) if i > 0]) - 200,
                 ymax=max([max(i) for i in y2data.values()]) + 200)
    ax2.set_xticks(kdates)
    ax2.set_ylabel(_(u"Daily rate (€)"))
    ax2.legend(plots2, [v for k, v in profils.items() if sum(y2data[k]) != 0],
              bbox_to_anchor=(0., 1.02, 1., .102), loc=4, ncol=4, borderaxespad=0.)
    ax2.grid(True)

    return print_png(fig)


@cache_page(60 * 10)
def graph_consultant_rates_pie(request, consultant_id):
    """Nice graph of consultant rates"""
    today = date.today()
    dateRange = ((_("Last 3 months"), today - timedelta(90)),
                 (_("Last 6 months"), today - timedelta(180)),
                 (_("Last 12 months"), today - timedelta(365)),
                 (_("Forever"), date(1970, 1, 1)))
    consultant = Consultant.objects.get(id=consultant_id)

    fig = Figure(figsize=(8, 8))
    fig.set_facecolor("white")

    # Rates pies
    for i, (title, refDate) in enumerate(dateRange):
        fc = consultant.getFinancialConditions(refDate, today)
        fc = fc.order_by('consultant__timesheet__charge__sum').reverse()[:6] # Only keep more important one
        fc = list(fc) # Swich to list because sliced qs cannot be sorted
        fc.sort(key=lambda x: x[0]) # sort on daily rates

        ax = fig.add_subplot(2, 2, i + 1)
        ax.pie([x[1] for x in fc], colors=COLORS,
           labels=[u"%s €\n(%s)" % (x[0], x[1]) for x in fc],
           shadow=True, autopct='%1.1f%%')
        ax.set_title(title)

    return print_png(fig)


@cache_page(60 * 10)
def graph_consultant_rates_graph(request, consultant_id):
    """Nice graph of consultant rates"""
    consultant = Consultant.objects.get(id=consultant_id)
    ydata = []
    fig = Figure(figsize=(8, 8))
    fig.set_facecolor("white")
    ax = fig.add_subplot(1, 1, 1)

    # Avg rate / month
    ts = Timesheet.objects.filter(consultant=consultant, charge__gt=0)
    kdates = ts.dates("working_date", "month")
    for refDate in kdates:
        nextMonth = (refDate + timedelta(40)).replace(day=1)
        fc = consultant.getFinancialConditions(refDate, nextMonth)
        if fc:
            ydata.append(sum([rate * days for rate, days in fc]) / sum([days for rate, days in fc]))
        else:
            ydata.append(None)

    if len([i for i in ydata if i > 0]) == 0:
        return print_png(fig)

    b = ax.plot(kdates, ydata, '-o', ms=10, lw=4, color=COLORS[0], mfc=COLORS[0])
    ax.legend(b, [_(u"Average daily rate (€)")], bbox_to_anchor=(0., 1.02, 1., .102),
              loc=4, ncol=4, borderaxespad=0.)
    ax.set_xticks(kdates)
    ax.set_xticklabels([d.strftime("%b %y") for d in kdates])
    ax.set_ylim(ymin=min(i for i in ydata if i > 0) - 100, ymax=max(ydata) + 100)

    return print_png(fig)
