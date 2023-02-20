#!/usr/bin/env python
# coding: utf-8

"""
Telegram bot for timesheet input and various reminder

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import sys
import os
from os.path import abspath, join, dirname, pardir
import logging
from datetime import date, datetime, time
import random
import pytz
from asgiref.sync import sync_to_async

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO,
)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, ConversationHandler, Application
import telegram.error

# # Setup django envt & django imports
PYDICI_DIR = abspath(join(dirname(__file__), pardir))
os.environ['DJANGO_SETTINGS_MODULE'] = "pydici.settings"

sys.path.append(PYDICI_DIR)  # Add project path to python path

# Ensure we are in the good current working directory (pydici home)
os.chdir(PYDICI_DIR)

# Django imports
from django.core.wsgi import get_wsgi_application
from django.db.models import Sum
from django.db import transaction, close_old_connections
from django.utils.translation import gettext as _
from django.conf import settings
from django.core.cache import cache


# Init and model loading
application = get_wsgi_application()

# Pydici imports
from people.models import Consultant
from staffing.models import Mission, Timesheet, Holiday
from core.utils import get_parameter

logger = logging.getLogger(__name__)

# Stages
MISSION_SELECT, MISSION_TIMESHEET = range(2)

NONPROD_BUTTON = InlineKeyboardButton(_("non productive mission?"), callback_data="NONPROD")
END_TIMESHEET_BUTTON = InlineKeyboardButton(_("That's all for today !"), callback_data="END")


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
    consultants = Consultant.objects.exclude(telegram_id=None).filter(active=True)
    return list(consultants)  # cast to list is needed to force qs evaluation in sync section


@sync_to_async
def mission_keyboard(consultant, nature):
    keyboard = []
    for mission in consultant.forecasted_missions():
        if mission.nature == nature:
            keyboard.append([InlineKeyboardButton(mission.short_name(), callback_data=str(mission.id)),])
    return keyboard


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


async def mission_timesheet(update, context):
    """Declare timesheet for given mission"""
    query = update.callback_query
    await query.answer()
    mission = await sync_to_async(Mission.objects.get)(id=int(query.data))
    context.user_data["mission"] = mission
    keyboard = [
        [
            InlineKeyboardButton("0", callback_data="0"),
            InlineKeyboardButton("0.25", callback_data="0.25"),
            InlineKeyboardButton("0.5", callback_data="0.5"),
            InlineKeyboardButton("0.75", callback_data="0.75"),
            InlineKeyboardButton("1", callback_data="1"),
        ]
    ]
    await query.edit_message_text(
        text=_("how much did you work on %(mission)s ? (%(time)s is remaining for today)") % {"mission": await sync_to_async(mission.short_name)(),
                                                                                              "time": 1 - sum(context.user_data["timesheet"].values())},
        reply_markup=InlineKeyboardMarkup(keyboard))
    return MISSION_TIMESHEET


async def end_timesheet(update, context):
    """Returns `ConversationHandler.END`, which tells the  ConversationHandler that the conversation is over"""
    query = update.callback_query
    await query.answer()

    try:
        msg = await update_timesheet(context)
    except Exception:
        await query.edit_message_text(text=_("Oups, cannot update your timesheet, sorry"))
        return ConversationHandler.END

    await query.edit_message_text(text=msg)
    return ConversationHandler.END

@sync_to_async
def update_timesheet(context):
    """Update consultant timesheet and return summary message"""
    consultant = context.user_data["consultant"]
    with transaction.atomic():
        Timesheet.objects.filter(consultant=consultant, working_date=date.today()).delete()
        for mission, charge in context.user_data["timesheet"].items():
            Timesheet.objects.create(mission=mission, consultant=consultant,
                                     charge=charge, working_date=date.today())
    msg = _("You timesheet was updated:\n")
    msg += " - "
    msg += "\n - ".join(["%s : %s" % (m.short_name(), c) for m, c in context.user_data["timesheet"].items()])
    total = sum(context.user_data["timesheet"].values())
    if total > 1:
        msg += _("\n\nWhat a day, %s declared. Time to get some rest!") % total
    elif total < 1:
        msg += _("\n\nOnly %s today. Don't you forget to declare something ?") % total
    return msg


async def select_mission(update, context):
    """Select mission to update"""
    query = update.callback_query
    await query.answer()
    consultant = context.user_data["consultant"]
    if query.data == "NONPROD":
        context.user_data["mission_nature"] = "NONPROD"
    else:
        mission = context.user_data["mission"]
        context.user_data["timesheet"][mission] = float(query.data)

    keyboard = await mission_keyboard(consultant, context.user_data["mission_nature"])

    if context.user_data["mission_nature"] == "PROD":
        keyboard.append([NONPROD_BUTTON, END_TIMESHEET_BUTTON])
    else:
        keyboard.append([END_TIMESHEET_BUTTON])

    await query.edit_message_text(text=_("On which other mission did you work today ?"), reply_markup=InlineKeyboardMarkup(keyboard))
    return MISSION_SELECT


async def declare_time(update, context):
    """Start timesheet session when user type /start"""
    close_old_connections()
    if update.effective_chat.id < 0:
        await update.message.reply_text(_("I am too shy to do that in public. Let's go private :-)"))
        return ConversationHandler.END

    consultant = await check_user_is_declared(update, context)
    if consultant is None:
        return ConversationHandler.END

    context.user_data["consultant"] = consultant
    context.user_data["mission_nature"] = "PROD"
    context.user_data["timesheet"] = {}

    keyboard = await mission_keyboard(consultant, "PROD")
    keyboard.append([NONPROD_BUTTON])

    await update.message.reply_text(_("On what did you work today ?"), reply_markup=InlineKeyboardMarkup(keyboard))

    return MISSION_SELECT


async def alert_consultant(context):
    """Randomly alert consultant about important stuff to do"""
    close_old_connections()
    if outside_business_hours():
        return

    consultants = await get_consultants()

    if not consultants:
        logger.warning("No consultant have telegram id defined. Alerting won't be possible. Bye")
        return
    consultant = random.choice(consultants)
    if await sync_to_async(consultant.is_in_holidays)():
        # don't bother people during holidays
        return
    cache_key = "BOT_ALERT_CONSULTANT_LAST_PERIOD_%s" % consultant.trigramme
    if cache.get(cache_key):
        # don't persecute people :-)
        return

    tasks = await sync_to_async(consultant.get_tasks)()
    if tasks:
        cache.set(cache_key, 1, 3600 * 12)  # Keep track 12 hours that this user has been alerted
        task_name, task_count, task_link, task_priority = random.choice(tasks)
        url = await sync_to_async(get_parameter)("HOST") + task_link
        msg = _("Hey, what about thinking about that: %(task_name)s (x%(task_count)s)\n%(link)s") % {"task_name": task_name,
                                                                                                     "task_count": task_count,
                                                                                                     "link": url.replace(" ", "%20")}
        try:
            await context.bot.send_message(chat_id=consultant.telegram_id, text=msg)
        except telegram.error.BadRequest as e:
            logger.error("Cannot send message to %s. Error message: %s" % (consultant, e))


async def call_for_timesheet(context):
    """If needed, remind people to declare timesheet of current day"""
    close_old_connections()
    if outside_business_hours():
        return
    msg = _("""Hope the day was fine. Time to declare your timesheet no? Just click /time""")

    consultants = await get_consultants()

    for consultant in consultants:
        if await time_to_declare(consultant) > 0:
            try:
                await context.bot.send_message(chat_id=consultant.telegram_id, text=msg)
            except telegram.error.Forbidden:
                # We have been banned :-( Opt out user
                consultant.telegram_id = None
                await sync_to_async(consultant.save)()


async def help(update, context):
    """Bot help"""
    close_old_connections()
    consultant = await check_user_is_declared(update, context)
    if consultant is None:
        return ConversationHandler.END
    msg = _("""Hello. I am just a bot you know. So I won't fake doing incredible things. Here's what can I do for you:
    /hello nice way to meet. After this cordial introduction, I may talk to you from time to time to remind you important things to do
    /time a fun and easy way to declare your timesheet of the day
    /bye you will never be bothered again till you say /hello again
    """)

    await update.message.reply_text(msg)

    return ConversationHandler.END


async def hello(update, context):
    """Bot introduction. Allow to receive alerts after this first meeting"""
    close_old_connections()
    consultant = await check_user_is_declared(update, context)
    if consultant is None:
        return ConversationHandler.END

    user = update.message.from_user

    if consultant.telegram_id:
        await update.message.reply_text(_("very happy to see you again !"))
    else:
        consultant.telegram_id = user.id
        await sync_to_async(consultant.save)()
        await update.message.reply_text(_("I very pleased to meet you !"))

    return ConversationHandler.END


async def bye(update, context):
    """Allow to erase consultant telegram id"""
    close_old_connections()
    consultant = await check_user_is_declared(update, context)
    if consultant is None:
        return ConversationHandler.END

    if consultant.telegram_id:
        await update.message.reply_text(_("I am so sad you leave me so early... Whenever you want to come back, just say /hello and we will be happy together again !"))
        consultant.telegram_id = None
        await sync_to_async(consultant.save)()
    else:
        await update.message.reply_text(_("Do we met ?"))

    return ConversationHandler.END

def main():
    token = os.environ.get("TELEGRAM_TOKEN", settings.TELEGRAM_TOKEN)
    application = Application.builder().token(token).http_version("1.1").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('time', declare_time),
                      CommandHandler("hello", hello),
                      CommandHandler("start", hello),
                      CommandHandler("bye", bye),
                      CommandHandler("help", help)],
        states={  # used for timesheet session only
            MISSION_SELECT: [
                CallbackQueryHandler(select_mission, pattern="NONPROD"),
                CallbackQueryHandler(end_timesheet, pattern="END"),
                CallbackQueryHandler(mission_timesheet),
            ],
            MISSION_TIMESHEET: [
                CallbackQueryHandler(select_mission),
            ],
        },
        fallbacks=[CommandHandler('help', help)],
    )

    # Add ConversationHandler to application
    application.add_handler(conv_handler)

    # Add alert job
    application.job_queue.run_repeating(alert_consultant, get_parameter("BOT_ALERT_INTERVAL"))

    # Add call for timesheet alert
    try:
        timesheet_time = time(*[int(i) for i in get_parameter("BOT_CALL_TIME_FOR_TIMESHEET").split(":")],
                              tzinfo=pytz.timezone(settings.TIME_ZONE))
    except (TypeError, ValueError):
        logger.error("Cannot parse timesheet time. Defaulting to 19:00")
        timesheet_time = time(19, tzinfo=pytz.timezone(settings.TIME_ZONE))
    application.job_queue.run_daily(call_for_timesheet, timesheet_time)

    try:
        # Start the Bot
        application.run_polling()

    except telegram.error.Forbidden:
        logger.error("Forbidden. Please check TELEGRAM_TOKEN settings")
        exit(1)

if __name__ == '__main__':
    main()
