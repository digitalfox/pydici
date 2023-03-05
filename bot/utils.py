# coding: utf-8
"""
Telegram bot utils.

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from asgiref.sync import sync_to_async
from datetime import datetime, date

from django.db import close_old_connections
from django.utils.translation import gettext as _

from people.models import Consultant
from staffing.models import Timesheet, Holiday


async def check_user_is_declared(update, context):
    """Ensure user we are talking  with is defined in our database. If yes, return consultant object"""
    try:
        user = update.message.from_user
        consultant = await sync_to_async(Consultant.objects.get)(telegram_alias="%s" % user.name.lstrip("@"), active=True)
        return consultant
    except Consultant.DoesNotExist:
        await update.message.reply_text(_("sorry, I don't know you"))
        return None
    except AttributeError:
        # User is editing a message. Don't answer
        return None


def outside_business_hours():
    """Don't bother people outside business hours"""
    now = datetime.now()
    return now.weekday() in (5, 6) or now.hour < 9 or now.hour > 19


@sync_to_async
def get_consultants():
    """:return: list of active consultants with declared telegram id"""
    close_old_connections()
    consultants = Consultant.objects.exclude(telegram_id=None).filter(active=True)
    return list(consultants)  # cast to list is needed to force qs evaluation in sync section


@sync_to_async()
def time_to_declare(consultant):
    today = date.today()
    holidays = Holiday.objects.all()
    if today.weekday() < 5 and today not in holidays:
        declared = Timesheet.objects.filter(consultant=consultant, working_date=today).aggregate(Sum("charge"))[
                       "charge__sum"] or 0
        return 1 - declared
    else:
        return 0
