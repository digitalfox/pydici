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
from django.db.models import Sum
from django.utils.translation import gettext as _
from django.utils import formats
from django.core.cache import cache

from staffing.models import Timesheet, Mission, LunchTicket, Holiday, Staffing
from core.utils import month_days, nextMonth, daysOfMonth, to_int_or_round
from people.models import TIMESHEET_IS_UP_TO_DATE_CACHE_KEY, CONSULTANT_IS_IN_HOLIDAYS_CACHE_KEY


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
        i = round(i, 4)  # We must round because using keyboard time input may lead to real numbers that are truncated
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

    return timesheetData, timesheetTotal, warning


@transaction.atomic
def saveTimesheetData(consultant, month, data, oldData):
    """Save user input timesheet in database"""
    previousMissionId = 0
    mission = None

    # Invalidate consultant cache stuff related to timesheet data
    cache.delete(TIMESHEET_IS_UP_TO_DATE_CACHE_KEY % consultant.__dict__)
    cache.delete(CONSULTANT_IS_IN_HOLIDAYS_CACHE_KEY % consultant.__dict__)

    for key, charge in data.items():
        if not charge and key not in oldData:
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


def updateHolidaysStaffing(consultant, month, missions, user):
    """Update holdays staffing to be at least equal to timesheet"""
    staffings_updated = []
    now = datetime.now()
    now = now.replace(microsecond=0)
    for mission in missions:
        if mission.nature == "HOLIDAYS":
            staffing, created = consultant.staffing_set.get_or_create(mission=mission, staffing_date=month)
            previous_charge = staffing.charge
            charge_sum = consultant.timesheet_set.filter(mission=mission, working_date__month=month.month, working_date__year=month.year).aggregate(Sum('charge'))["charge__sum"] or 0
            new_charge = max(charge_sum, staffing.charge)  # We don't want to reduce staffing
            if previous_charge != new_charge:
                staffing.charge = new_charge
                staffing.update_date = now
                staffing.last_user = str(user)
                staffing.save()
                staffings_updated.append((mission, previous_charge, new_charge))
    return staffings_updated


@transaction.atomic
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
            staffing.last_user = str(request.user)
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
            print("Unknown mission nature (%s). Cannot sort" % mission.nature)

    # Sort each list
    holidaysMissions.sort(key=lambda x: str(x.description))
    nonProdMissions.sort(key=lambda x: str(x.description))
    prodMissions.sort(key=lambda x: str(x))

    return prodMissions + nonProdMissions + holidaysMissions


def holidayDays(month=None):
    """
    @param month: month (datetime) to consider for holidays. Current month if None
    @return: list of holidays days of given month """
    if not month:
        month = date.today()
    month = month.replace(day=1)
    return [h.day for h in Holiday.objects.filter(day__gte=month).filter(day__lt=nextMonth(month))]


def staffingDates(n=12, format=None, minDate=None, maxDate=None):
    """Returns a list of n next month as datetime (if format="datetime") or
    as a list of dict() with short/long(encoded) string date"""
    staffingDate = minDate or date.today().replace(day=1)
    dates = []
    for i in range(int(n)):
        if format == "datetime":
            dates.append(staffingDate)
        else:
            dates.append({"value": formats.localize_input(staffingDate),
                          "label": formats.date_format(staffingDate, format="YEAR_MONTH_FORMAT").encode("latin-1"), })
        staffingDate = nextMonth(staffingDate)
        if maxDate and staffingDate > maxDate:
            break
    return dates


def time_string_for_day_percent(day_percent, day_duration=settings.TIMESHEET_DAY_DURATION):
    if day_percent is None:
        return ""
    else:
        # Using round() is important here because int() truncates the decimal
        # part so int(24.99) returns 24, whereas round(24.99) returns 25.
        total_minutes = int(round(day_percent * day_duration * 60))
        hours = int(total_minutes / 60)
        minutes = total_minutes % 60
    return '{}:{:02}'.format(hours, minutes)


def day_percent_for_time_string(time_string, day_duration=settings.TIMESHEET_DAY_DURATION):
    value_struct = time.strptime(time_string, '%H:%M')
    duration = value_struct[3] + value_struct[4] / 60.0
    return duration / day_duration


def timesheet_report_data_grouped(mission, start=None, end=None):
    """Timesheet charges for a single mission, on a timerange, by whole month
    For each month, charges are grouped by daily rate
    Returns a list of lines to be sent as CSV"""

    timesheets = Timesheet.objects.select_related().filter(mission=mission)
    months = timesheets.dates("working_date", "month")
    data = []

    data.append([mission.short_name()])
    rates_consultants = {}
    for consultant, rate in mission.consultant_rates().items():
        daily_rate, _ = rate
        if daily_rate not in rates_consultants:
            rates_consultants[daily_rate] = []
        rates_consultants[daily_rate].append(consultant)

    for month in months:
        if start and month < start:
            continue
        if end and month > end:
            break
        next_month = nextMonth(month)

        # Header
        data.append([""])
        data.append([formats.date_format(month, format="YEAR_MONTH_FORMAT")])

        rates = sorted(rates_consultants.keys())
        for rate in rates:
            rate_label = "R {}".format(rate)
            total = 0
            row = [rate_label, ]

            # timesheets is already a Queryset, we cannot aggregate in SQL
            rate_timesheets_charges = timesheets.filter(consultant__in=rates_consultants[rate],
                                                        working_date__gte=month,
                                                        working_date__lt=next_month).values("charge")

            for c in rate_timesheets_charges:
                total += c["charge"]
            row.append(total)

            if total:
                data.append(row)

    return data


def timesheet_report_data(mission, start=None, end=None, padding=False):
    """Prepare data for timesheet report from start to end.
    Padding align total in the same column"""
    timesheets = Timesheet.objects.select_related().filter(mission=mission)
    months = timesheets.dates("working_date", "month")
    data = []

    for month in months:
        if start and month < start:
            continue
        if end and month > end:
            break
        days = daysOfMonth(month)
        next_month = nextMonth(month)
        padding_length = 31 - len(days)  # Padding for month with less than 31 days to align total column
        # Header
        data.append([""])
        data.append([formats.date_format(month, format="YEAR_MONTH_FORMAT")])

        # Days
        data.append(["", ] + [d.day for d in days])
        dayHeader = [_("Consultants")] + [_(d.strftime("%a")) for d in days]
        if padding:
            dayHeader.extend([""] * padding_length)
        dayHeader.append(_("total"))
        data.append(dayHeader)

        for consultant in mission.consultants():
            total = 0
            row = [consultant, ]
            consultant_timesheets = {}
            for timesheet in timesheets.filter(consultant_id=consultant.id,
                                               working_date__gte=month,
                                               working_date__lt=next_month):
                consultant_timesheets[timesheet.working_date] = timesheet.charge
            for day in days:
                try:
                    charge = consultant_timesheets.get(day)
                    if charge:
                        row.append(formats.number_format(to_int_or_round(charge, 2)))
                        total += charge
                    else:
                        row.append("")
                except Timesheet.DoesNotExist:
                    row.append("")
            if padding:
                row.extend([""] * padding_length)
            row.append(formats.number_format(to_int_or_round(total, 2)))
            if total > 0:
                data.append(row)

    return data


def create_next_year_std_missions(current, target, dryrun=True, start_date=None, end_date=None):
    """Create default set of mission for next year based on current holidays and nonprod missions
    @current: current suffix
    @target: target suffix
    @dryrun: save new mission or just print its
    @start_date: mission start boundary
    @end_date: mission end boundary"""
    for m in Mission.objects.exclude(nature="PROD").filter(active=True):
        if not m.description or current not in m.description:
            continue
        new_mission = Mission(description=m.description.replace(current, target),
                              subsidiary=m.subsidiary,
                              nature=m.nature,
                              billing_mode="TIME_SPENT",
                              probability=100,
                              probability_auto=False,
                              analytic_code=m.analytic_code,
                              start_date=start_date,
                              end_date=end_date,
                              min_charge_multiple_per_day=m.min_charge_multiple_per_day,
                              always_displayed=m.always_displayed)
        print("Creating new mission %s" % new_mission)
        if not dryrun:
            new_mission.save()


def check_missions_limited_mode(missions):
    """Ensure that after a timesheet update we don't violate limited management mode policy
    :return list of missions that do not conform to policy"""
    offending_missions = []
    for mission in missions:
        if mission.management_mode == "LIMITED":
            if mission.remaining(mode="current") < 0:
                offending_missions.append(mission)
    return offending_missions


def check_missions_limited_individual_mode(missions, consultant, month):
    """Ensure that after a timesheet update for this consultant on this month we don't violate individual limited management mode policy
    :return list of missions that do not conform to policy"""
    offending_missions = []
    for mission in missions:
        if mission.management_mode == "LIMITED_INDIVIDUAL":
            timesheet = Timesheet.objects.filter(mission=mission, consultant=consultant,
                                                 working_date__gte=month, working_date__lt=nextMonth(month))
            timesheet = timesheet.aggregate(Sum("charge")).get("charge__sum", 0) or 0
            forecast = Staffing.objects.filter(mission=mission, consultant=consultant, staffing_date=month)
            forecast = forecast.aggregate(Sum("charge")).get("charge__sum", 0) or 0
            if forecast < timesheet:
                offending_missions.append(mission)
    return offending_missions


def check_missions_charge_multiple(missions, month):
    """Ensure that after a timesheet update on this month we don't violate minimum charge per day requirement
    :return list of missions that do not conform to policy"""
    offending_missions = []
    for mission in missions:
        if mission.min_charge_multiple_per_day == 0:
            continue
        charges = Timesheet.objects.filter(mission=mission, working_date__gte=month, working_date__lt=nextMonth(month),
                                           charge__gt=0).values_list("charge", flat=True)

        if sum([i % mission.min_charge_multiple_per_day for i in charges]):
            offending_missions.append(mission)

    return offending_missions


def check_timesheet_validity(missions, consultant, month):
    """Execute all check that must be done before saving timesheet.
    It's up to the caller to encapsulate this in a transaction and commit or rollback according to results
    Checks done: check_missions_limited_mode, check_missions_limited_individual_mode, check_missions_charge_multiple
    :return potential errors or None if everything is fine"""
    limited_mode_offending_missions = check_missions_limited_mode(missions)
    if limited_mode_offending_missions:
        return _("Timesheet exceeds mission price and management is set as 'limited' (%s)") %\
            ", ".join([str(m) for m in limited_mode_offending_missions])
    charge_multiple_offending_missions = check_missions_charge_multiple(missions, month)
    if charge_multiple_offending_missions:
        return _("Charge must be a multiple (%s)") %\
            ", ".join([f"{m} : {m.min_charge_multiple_per_day} "for m in charge_multiple_offending_missions])
    limited_individual_mode_offending_missions = check_missions_limited_individual_mode(missions, consultant, month)
    if limited_individual_mode_offending_missions:
        return _("Charge cannot exceed forecast (%s)") %\
            ", ".join([str(m) for m in limited_individual_mode_offending_missions])


def compute_mission_consultant_rates(mission):
    """helper function to compute mission rates for each consultant for tab display and htmx edit form"""
    rates = {}
    objective_rates = mission.consultant_objective_rates()
    for consultant, rate in mission.consultant_rates().items():
        rates[consultant] = (rate, objective_rates.get(consultant))
    try:
        objective_dates = [i[0] for i in list(objective_rates.values())[0]]
    except IndexError:
        # No consultant or no objective on mission timeframe
        objective_dates = []
    return objective_dates, rates


def is_outside_business_hours(date_with_time=None):
    """Don't bother people outside business hours and during holidays"""
    if date_with_time is None:
        date_with_time = datetime.now()
    is_not_working = Holiday.objects.filter(day=date_with_time.date()).exists()
    is_not_working = is_not_working or date_with_time.weekday() in (5, 6) or date_with_time.hour < 9 or date_with_time.hour > 19
    return is_not_working
