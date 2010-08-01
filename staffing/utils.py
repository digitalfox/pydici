# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in Staffing models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from django.db import transaction

from pydici.staffing.models import Timesheet, Mission

def gatherTimesheetData(consultant, missions, month):
    """Gather existing timesheet timesheetData
    @returns: (timesheetData, timesheetTotal)
    timesheetData represent timesheet form post timesheetData as a dict
    timesheetTotal is a dict of total charge (key is mission id)"""
    timesheetData = {}
    timesheetTotal = {}
    for mission in missions:
        for timesheet in Timesheet.objects.select_related().filter(consultant=consultant).filter(mission=mission):
            if timesheet.working_date.month == month.month:
                timesheetData["charge_%s_%s" % (timesheet.mission.id, timesheet.working_date.day)] = timesheet.charge
                if mission.id in timesheetTotal:
                    timesheetTotal[mission.id] += timesheet.charge
                else:
                    timesheetTotal[mission.id] = timesheet.charge
    return (timesheetData, timesheetTotal)

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
        if missionId != previousMissionId:
            mission = Mission.objects.get(id=missionId)
            previousMissionId = missionId
        working_date = month.replace(day=day)
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
