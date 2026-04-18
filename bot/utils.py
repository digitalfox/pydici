# coding: utf-8
"""
Telegram bot utils.

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from asgiref.sync import SyncToAsync
from datetime import date

from django.db import close_old_connections
from django.db.models import Sum
from django.utils.translation import gettext as _

from people.models import Consultant

from staffing.models import Timesheet


class DbSyncToAsync(SyncToAsync):
    """SyncToAsync with database connection close. Kindly borrowed from the Django Channels Projets"""
    def thread_handler(self, loop, *args, **kwargs):
        close_old_connections()
        try:
            return super().thread_handler(loop, *args, **kwargs)
        finally:
            close_old_connections()

# decorator/callable
db_sync_to_async = DbSyncToAsync

async def check_user_is_declared(update, context):
    """Ensure user we are talking  with is defined in our database. If yes, return consultant object"""
    try:
        user = update.message.from_user
        consultant = await db_sync_to_async(Consultant.objects.get)(telegram_alias="%s" % user.name.lstrip("@"), active=True)
        return consultant
    except Consultant.DoesNotExist:
        await update.message.reply_text(_("sorry, I don't know you"))
        return None
    except AttributeError:
        # User is editing a message. Don't answer
        return None


@db_sync_to_async
def get_consultants():
    """:return: list of active consultants with declared telegram id"""
    consultants = Consultant.objects.exclude(telegram_id=None).filter(active=True)
    return list(consultants)  # cast to list is needed to force qs evaluation in sync section


@db_sync_to_async
def time_to_declare(consultant):
    today = date.today()
    declared = Timesheet.objects.filter(consultant=consultant, working_date=today).aggregate(Sum("charge"))[
                    "charge__sum"] or 0
    return 1 - declared
