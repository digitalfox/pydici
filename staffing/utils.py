# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in Staffing models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
import time

from datetime import date, datetime

from django.conf import settings
from django.db import transaction
from django.utils import formats

from staffing.models import Timesheet, Mission, LunchTicket, Holiday
from core.utils import month_days, nextMonth, daysOfMonth


def gatherTimesheetData(consultant, missions, month):
    """Gather existing timesheet timesheetData
    @returns: (timesheetData, timesheetTotal, warning)
    timesheetData represent timesheet form post timesheetData as a dict
    timesheetTotal is a dict of total charge (key is mission id)
    warning is a list of 0 (ok) or 1 (surbooking) or 2 (no data). One entry per day"""
    timesheetData = {}
    timesheetTotal = {}
    warning = []
    totalPerDay = [0] * month_days(month)
    next_month = nextMonth(month)
    for mission in missions:
        timesheets = Timesheet.objects.select_related().filter(consultant=consultant).filter(mission=mission)
        timesheets = timesheets.filter(working_date__gte=month).filter(working_date__lt=next_month)
        for timesheet in timesheets:
            timesheetData["charge_%s_%s" % (timesheet.mission.id, timesheet.working_date.day)] = timesheet.charge
            if mission.id in timesheetTotal:
                timesheetTotal[mission.id] += timesheet.charge
            else:
                timesheetTotal[mission.id] = timesheet.charge
            totalPerDay[timesheet.working_date.day - 1] += timesheet.charge
    # Gather lunck ticket data
    totalTicket = 0
    lunchTickets = LunchTicket.objects.filter(consultant=consultant)
    lunchTickets = lunchTickets.filter(lunch_date__gte=month).filter(lunch_date__lt=next_month)
    for lunchTicket in lunchTickets:
        timesheetData["lunch_ticket_%s" % lunchTicket.lunch_date.day] = lunchTicket.no_ticket
        totalTicket += 1
    timesheetTotal["ticket"] = totalTicket
    # Compute warnings (overbooking and no data)
    for i in totalPerDay:
        if i > 1:  # Surbooking
            warning.append(1)
        elif i == 1:  # Ok
            warning.append(0)
        else:  # warning (no data, or half day)
            warning.append(2)
    # Don't emit warning for no data during week ends and holidays
    holiday_days = holidayDays(month)
    for day in daysOfMonth(month):
        if day.isoweekday() in (6, 7) or day in holiday_days:
            warning[day.day - 1] = None

    return (timesheetData, timesheetTotal, warning)


@transaction.atomic
def saveTimesheetData(consultant, month, data, oldData):
    """Save user input timesheet in database"""
    previousMissionId = 0
    mission = None
    for key, charge in data.items():
        if not charge and not key in oldData:
            # No charge in new and old data
            continue
        if charge and key in oldData and float(data[key]) == oldData[key]:
            # Data does not changed - skip it
            continue
        (foo, missionId, day) = key.split("_")
        day = int(day)
        working_date = month.replace(day=day)
        if missionId == "ticket":
            # Lunch ticket handling
            lunchTicket, created = LunchTicket.objects.get_or_create(consultant=consultant,
                                                                    lunch_date=working_date)
            if charge:
                # Create/update new data
                lunchTicket.no_ticket = True
                lunchTicket.save()
            else:
                lunchTicket.delete()
        else:
            # Standard mission handling
            if missionId != previousMissionId:
                mission = Mission.objects.get(id=missionId)
                previousMissionId = missionId
            timesheet, created = Timesheet.objects.get_or_create(consultant=consultant,
                                                                 mission=mission,
                                                                 working_date=working_date)
            if charge:
                # create/update new data
                timesheet.charge = charge
                timesheet.save()
            else:
                # remove data user just deleted
                timesheet.delete()


def saveFormsetAndLog(formset, request):
    """Save the given staffing formset and log last user"""
    now = datetime.now()
    now = now.replace(microsecond=0)  # Remove useless microsecond that pollute form validation in callback
    formset.save()
    deleted_forms = list(formset.deleted_forms)
    for form in formset.forms:
        if form in deleted_forms:
            # Don't consider forms marked for deletion
            continue
        if form.changed_data and form.changed_data != ["update_date"]:  # don't consider update_date as L10N formating mess up has_changed widget method
            staffing = form.save()
            staffing.last_user = unicode(request.user)
            staffing.update_date = now
            staffing.save()


def sortMissions(missions):
    """Sort mission list in the following way:
         - first, prod mission, alpha sort on __unicode__ repr
         - second, non prod mission, alpha sorted on description
         - last, holidays missions, alpha sorted on description
    @param missions: list of missions
    @return: sorted mission list"""
    holidaysMissions = []
    nonProdMissions = []
    prodMissions = []
    # Separate missions according nature
    for mission in missions:
        if mission.nature == "HOLIDAYS":
            holidaysMissions.append(mission)
        elif mission.nature == "NONPROD":
            nonProdMissions.append(mission)
        elif mission.nature == "PROD":
            prodMissions.append(mission)
        else:
            # Oups, we should never go here. Just log, in case of
            print "Unknown mission nature (%s). Cannot sort" % mission.nature

    # Sort each list
    holidaysMissions.sort(key=lambda x: x.description)
    nonProdMissions.sort(key=lambda x: x.description)
    prodMissions.sort(key=lambda x: unicode(x))

    return prodMissions + nonProdMissions + holidaysMissions


def holidayDays(month=None):
    """
    @param month: month (datetime) to consider for holidays. Current month if None
    @return: list of holidays days of given month """
    if not month:
        month = date.today()
    month = month.replace(day=1)
    return [h.day for h in  Holiday.objects.filter(day__gte=month).filter(day__lt=nextMonth(month))]


def staffingDates(n=12, format=None, minDate=None):
    """Returns a list of n next month as datetime (if format="datetime") or
    as a list of dict() with short/long(encoded) string date"""
    staffingDate = minDate or date.today().replace(day=1)
    dates = []
    for i in range(n):
        if format == "datetime":
            dates.append(staffingDate)
        else:
            dates.append({"value": formats.localize_input(staffingDate),
                          "label": formats.date_format(staffingDate, format="YEAR_MONTH_FORMAT").encode("latin-1"), })
        staffingDate = nextMonth(staffingDate)
    return dates


def time_string_for_day_percent(day_percent, day_duration=settings.TIMESHEET_DAY_DURATION):
    if day_percent is None:
        hours = 0
        minutes = 0
    else:
        # Using round() is important here because int() truncates the decimal
        # part so int(24.99) returns 24, whereas round(24.99) returns 25.
        total_minutes = int(round(day_percent * day_duration * 60))
        hours = total_minutes / 60
        minutes = total_minutes % 60
    return '{}:{:02}'.format(hours, minutes)


def day_percent_for_time_string(time_string, day_duration=settings.TIMESHEET_DAY_DURATION):
    value_struct = time.strptime(time_string, '%H:%M')
    duration = value_struct[3] + value_struct[4] / 60.0
    return duration / day_duration
