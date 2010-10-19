# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in Staffing models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from datetime import datetime, timedelta

from django.db import transaction

from pydici.staffing.models import Timesheet, Mission, LunchTicket
from pydici.core.utils import month_days

def gatherTimesheetData(consultant, missions, month):
    """Gather existing timesheet timesheetData
    @returns: (timesheetData, timesheetTotal, overbooking)
    timesheetData represent timesheet form post timesheetData as a dict
    timesheetTotal is a fffddict of total charge (key is mission id)
    overbooking is a list of 0 (no surbooking) or 1 (surbooking). One entry per day"""
    timesheetData = {}
    timesheetTotal = {}
    overbooking = []
    totalPerDay = [0] * month_days(month)
    next_month = (month + timedelta(days=40)).replace(day=1)
    for mission in missions:
        for timesheet in Timesheet.objects.select_related().filter(consultant=consultant).filter(mission=mission):
            if timesheet.working_date.month == month.month:
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
    # Compute overbooking
    for i in totalPerDay:
        if i > 1:
            overbooking.append(1)
        else:
            overbooking.append(0)
    return (timesheetData, timesheetTotal, overbooking)

@transaction.commit_on_success
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
            print "ticket"
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
    now = now.replace(microsecond=0) # Remove useless microsecond that pollute form validation in callback
    staffings = formset.save(commit=False)
    for staffing in staffings:
        staffing.last_user = unicode(request.user)
        staffing.update_date = now
        staffing.save()

