# coding: utf-8

"""
Module that handle asynchronous tasks
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta, datetime
from celery import shared_task

from django.urls import reverse
from django.core.mail import send_mass_mail
from django.utils.translation import gettext as _
from django.template.loader import get_template

from core.utils import get_parameter
from people.models import Consultant
from staffing.models import Holiday
from staffing.utils import gatherTimesheetData


@shared_task
def warn_for_incomplete_timesheet(warn_overbooking=False, days=None, month="last"):
    """Warn users and admin for incomplete timesheet after due date
    :param warn_overbooking: Warn for overbooking days (default is false)
    :param days: only check n first days. If None (default), check all month
    :param month: Month to check: current or last (default) month"""

    # Don't send mail weekend or holiday
    today = datetime.today()
    if today.weekday() in (5, 6) or Holiday.objects.filter(day=today).exists():
        return

    email_template = get_template("batch/timesheet_warning_email.txt")
    if month == "current":
        #TODO use core.utils nextMonth()
        nextMonth = (date.today().replace(day=1) + timedelta(days=40)).replace(day=1)
        currentMonth = date.today().replace(day=1)
    elif month == "last":
        # Checking past month
        nextMonth = date.today().replace(day=1)
        # TODO use core.utils.previousMonth()
        currentMonth = (nextMonth - timedelta(days=5)).replace(day=1)
    else:
        raise Exception("month parameter must be one of 'last' or 'current'")

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
        url += "?year=%s&month=%s" % (currentMonth.year, currentMonth.month)
        url += "#tab-timesheet"

        # Truncate if day parameter was given
        if days:
            warning = warning[:days]
        warning = [i for i in warning if i]  # Remove None
        if sum(warning) > 0:
            overbooking_days = warning.count(1)
            incomplete_days = warning.count(2)
            if not warn_overbooking and not incomplete_days:
                continue  # Don't cry if user only have overbooking issue

            user = consultant.get_user()
            if user and user.email:
                recipients.append(user.email)
            if consultant.manager:
                managerUser = consultant.manager.get_user()
                if managerUser and managerUser.email:
                    recipients.append(managerUser.email)

            if recipients:
                msgText = email_template.render(context={"month": currentMonth,
                                                        "surbooking_days": overbooking_days,
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
