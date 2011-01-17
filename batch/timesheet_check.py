#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Pydici batch module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

# python import 
from datetime import date, timedelta
from os.path import abspath, dirname, join, pardir
import sys
import os
from optparse import OptionParser

# Ensure we are in the good current working directory (pydici home)
os.chdir(abspath(join(dirname(__file__), pardir)))

## Setup django envt & django imports
sys.path.append(abspath(join(dirname(__file__), pardir))) # Add project path to python path
from django.core.management import setup_environ, execute_manager
import settings
setup_environ(settings)

# Django import
from django.core import urlresolvers
from django.core.mail import send_mass_mail
from django.utils.translation import ugettext as _
from django.template.loader import get_template
from django.template import Context

# Pydici imports
from pydici.staffing.models import Timesheet, Mission
from pydici.people.models import Consultant
from pydici.staffing.utils import gatherTimesheetData
import pydici.settings



def warnForImcompleteTimesheet(warnSurbooking=False, days=None, month=None):
    """Warn users and admin for incomplete timesheet after due date
    @param warnSurbooking: Warn for surbooking days (default is false)
    @param day: only check n first days. If none, check all month"""
    emailTemplate = get_template("batch/timesheet_warning_email.txt")
    if month == "current":
        nextMonth = (date.today().replace(day=1) + timedelta(days=40)).replace(day=1)
        currentMonth = (nextMonth - timedelta(days=5)).replace(day=1)
    else:
        # Checking past month
        nextMonth = date.today().replace(day=1)
        currentMonth = (nextMonth - timedelta(days=5)).replace(day=1)

    mails = [] # List of mail to be sent
    for consultant in Consultant.objects.filter(active=True):
        recipients = []
        missions = consultant.timesheet_missions(month=currentMonth)
        timesheetData, timesheetTotal, warning = gatherTimesheetData(consultant, missions, currentMonth)
        url = pydici.settings.PYDICI_HOST + urlresolvers.reverse("pydici.staffing.views.consultant_timesheet", args=[consultant.id, currentMonth.year, currentMonth.month])
        # Truncate if day parameter was given
        if days:
            warning = warning[:days]
        warning = [i for i in warning if i] # Remove None 
        if sum(warning) > 0:
            surbookingDays = warning.count(1)
            incompleteDays = warning.count(2)
            if not warnSurbooking and not incompleteDays:
                continue # Don't cry if user only have surbooking issue                

            user = consultant.getUser()
            if user and user.email:
                recipients.append(user.email)
            if consultant.manager:
                managerUser = consultant.manager.getUser()
                if managerUser and managerUser.email:
                    recipients.append(managerUser.email)

            if recipients:
                msgText = emailTemplate.render(Context(
                                            {"month": currentMonth,
                                             "surbooking_days" : surbookingDays,
                                             "incomplete_days" : incompleteDays,
                                             "consultant" : consultant,
                                             "url": url }))
                mails.append(((_("[pydici] Your timesheet is not correct"), msgText,
                          pydici.settings.LEADS_MAIL_FROM, recipients)))
            else:
                mails.append(((_("[pydici] User has no email"),
                               _("User %s has an incomplete timesheet but cannot be warned because he has no email." % consultant),
                          pydici.settings.LEADS_MAIL_FROM, [pydici.settings.LEADS_MAIL_FROM, ])))

    # Send all emails in one time
    send_mass_mail(mails, fail_silently=False)


def parseOptions():
    """Command line option parsing"""
    parser = OptionParser()

    # Pages generation
    parser.add_option("-w", "--warnSurbooking", dest="warnSurbooking",
                      action="store_true", default="False",
                      help="Warn even if user has only surbooking issue")
    parser.add_option("-d", "--days", dest="days", type="int", default=None,
                      help="Only check the first n days of the month instead of the whole month.")
    parser.add_option("-m", "--month", dest="month", type="choice",
                      choices=["current", "last"], default="last",
                      help="Month to check: current or last.")
    return parser.parse_args()

if __name__ == "__main__":
    (options, args) = parseOptions()
    warnForImcompleteTimesheet(warnSurbooking=True,
                               days=options.days,
                               month=options.month)
