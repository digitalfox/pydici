#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Pydici batch module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""


# python import
from datetime import date, timedelta
from os.path import abspath, dirname, join, pardir
import sys
import os
from optparse import OptionParser

# # Setup django envt & django imports
PYDICI_DIR = abspath(join(dirname(__file__), pardir))
os.environ['DJANGO_SETTINGS_MODULE'] = "pydici.settings"

sys.path.append(PYDICI_DIR)  # Add project path to python path

# Ensure we are in the good current working directory (pydici home)
os.chdir(PYDICI_DIR)

# Django import
from django.urls import reverse
from django.core.mail import send_mass_mail
from django.core.wsgi import get_wsgi_application
from django.utils.translation import ugettext as _
from django.template.loader import get_template

# Init and model loading
application = get_wsgi_application()

# Pydici imports
from core.utils import get_parameter
from people.models import Consultant
from staffing.utils import gatherTimesheetData


def warn_for_imcomplete_timesheet(warn_surbooking=False, days=None, month=None):
    """Warn users and admin for incomplete timesheet after due date
    @param warn_surbooking: Warn for surbooking days (default is false)
    @param day: only check n first days. If none, check all month"""
    email_template = get_template("batch/timesheet_warning_email.txt")
    if month == "current":
        nextMonth = (date.today().replace(day=1) + timedelta(days=40)).replace(day=1)
        currentMonth = date.today().replace(day=1)
    else:
        # Checking past month
        nextMonth = date.today().replace(day=1)
        currentMonth = (nextMonth - timedelta(days=5)).replace(day=1)

    mails = []  # List of mail to be sent
    for consultant in Consultant.objects.filter(active=True, subcontractor=False):
        recipients = []
        if not [m for m in consultant.forecasted_missions(currentMonth) if m.nature == "PROD"]:
            # No productive mission forecasted on current month
            # Consultant may have just started
            # No check needed. Skip it
            continue
        missions = consultant.timesheet_missions(month=currentMonth)
        timesheet_data, timesheet_total, warning = gatherTimesheetData(consultant, missions, currentMonth)
        url = get_parameter("HOST") + reverse("people:consultant_home", args=[consultant.trigramme])
        url += "?year=%s;month=%s" % (currentMonth.year, currentMonth.month)
        url += "#tab-timesheet"

        # Truncate if day parameter was given
        if days:
            warning = warning[:days]
        warning = [i for i in warning if i]  # Remove None
        if sum(warning) > 0:
            surbooking_days = warning.count(1)
            incomplete_days = warning.count(2)
            if not warn_surbooking and not incomplete_days:
                continue  # Don't cry if user only have surbooking issue

            user = consultant.get_user()
            if user and user.email:
                recipients.append(user.email)
            if consultant.manager:
                managerUser = consultant.manager.get_user()
                if managerUser and managerUser.email:
                    recipients.append(managerUser.email)

            if recipients:
                msgText = email_template.render(context={"month": currentMonth,
                                                        "surbooking_days": surbooking_days,
                                                        "incomplete_days": incomplete_days,
                                                        "consultant": consultant,
                                                        "days": days,
                                                        "url": url})
                mails.append(((_("[pydici] Your timesheet is not correct"), msgText,
                          get_parameter("MAIL_FROM"), recipients)))
            else:
                mails.append(((_("[pydici] User has no email"),
                               _("User %s has an incomplete timesheet but cannot be warned because he has no email." % consultant),
                               get_parameter("MAIL_FROM"), [get_parameter("MAIL_FROM"), ])))

    # Send all emails in one time
    send_mass_mail(mails, fail_silently=False)


def parse_options():
    """Command line option parsing"""
    parser = OptionParser()

    # Pages generation
    parser.add_option("-w", "--warnSurbooking", dest="warn_surbooking",
                      action="store_true", default=False,
                      help="Warn even if user has only surbooking issue")
    parser.add_option("-d", "--days", dest="days", type="int", default=None,
                      help="Only check the first n days of the month instead of the whole month.")
    parser.add_option("-m", "--month", dest="month", type="choice",
                      choices=["current", "last"], default="last",
                      help="Month to check: current or last.")
    return parser.parse_args()


if __name__ == "__main__":
    (options, args) = parse_options()
    warn_for_imcomplete_timesheet(warn_surbooking=options.warn_surbooking, days=options.days, month=options.month)
