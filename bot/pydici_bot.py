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
from datetime import time
import random
import pytz

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO,
)

from telegram.ext import CommandHandler, ConversationHandler
from telegram.ext import Application as TelegramApplication
import telegram.error

# # Setup django envt & django imports
PYDICI_DIR = abspath(join(dirname(__file__), pardir))
os.environ['DJANGO_SETTINGS_MODULE'] = "pydici.settings"

sys.path.append(PYDICI_DIR)  # Add project path to python path

# Ensure we are in the good current working directory (pydici home)
os.chdir(PYDICI_DIR)

# Django imports
from django.core.wsgi import get_wsgi_application
from django.utils.translation import gettext as _
from django.conf import settings
from django.core.cache import cache


# Init and model loading
application = get_wsgi_application()

# Pydici imports
from core.utils import get_parameter

# Bot import
from bot.utils import check_user_is_declared, outside_business_hours, get_consultants, time_to_declare, db_sync_to_async
from bot.declare_timesheet import declare_time_entry_points, declare_time_states

logger = logging.getLogger(__name__)


async def alert_consultant(context):
    """Randomly alert consultant about important stuff to do"""
    if outside_business_hours():
        return

    consultants = await get_consultants()

    if not consultants:
        logger.warning("No consultant have telegram id defined. Alerting won't be possible. Bye")
        return
    consultant = random.choice(consultants)
    if await db_sync_to_async(consultant.is_in_holidays)():
        # don't bother people during holidays
        return
    cache_key = "BOT_ALERT_CONSULTANT_LAST_PERIOD_%s" % consultant.trigramme
    if cache.get(cache_key):
        # don't persecute people :-)
        return

    tasks = await db_sync_to_async(consultant.get_tasks)()
    if tasks:
        cache.set(cache_key, 1, 3600 * 12)  # Keep track 12 hours that this user has been alerted
        task = random.choice(tasks)
        url = await db_sync_to_async(get_parameter)("HOST") + task.link
        msg = _("Hey, what about thinking about that: %(task_name)s (x%(task_count)s)\n%(link)s") % {"task_name": task.label,
                                                                                                     "task_count": task.count,
                                                                                                     "link": url.replace(" ", "%20")}
        try:
            await context.bot.send_message(chat_id=consultant.telegram_id, text=msg)
        except telegram.error.BadRequest as e:
            logger.error("Cannot send message to %s. Error message: %s" % (consultant, e))


async def call_for_timesheet(context):
    """If needed, remind people to declare timesheet of current day"""
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
                await db_sync_to_async(consultant.save)()


async def help(update, context):
    """Bot help"""
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
    consultant = await check_user_is_declared(update, context)
    if consultant is None:
        return ConversationHandler.END

    user = update.message.from_user

    if consultant.telegram_id:
        await update.message.reply_text(_("very happy to see you again !"))
    else:
        consultant.telegram_id = user.id
        await db_sync_to_async(consultant.save)()
        await update.message.reply_text(_("I very pleased to meet you !"))

    return ConversationHandler.END


async def bye(update, context):
    """Allow to erase consultant telegram id"""
    consultant = await check_user_is_declared(update, context)
    if consultant is None:
        return ConversationHandler.END

    if consultant.telegram_id:
        await update.message.reply_text(_("I am so sad you leave me so early... Whenever you want to come back, just say /hello and we will be happy together again !"))
        consultant.telegram_id = None
        await db_sync_to_async(consultant.save)()
    else:
        await update.message.reply_text(_("Do we met ?"))

    return ConversationHandler.END

def main():
    token = os.environ.get("TELEGRAM_TOKEN", settings.TELEGRAM_TOKEN)
    application = TelegramApplication.builder().token(token).http_version("1.1").get_updates_http_version("1.1").build()

    entry_points = [CommandHandler("hello", hello),
                    CommandHandler("start", hello),
                    CommandHandler("bye", bye),
                    CommandHandler("help", help)]
    entry_points.extend(declare_time_entry_points())

    states = {}
    states.update(declare_time_states())

    conv_handler = ConversationHandler(entry_points=entry_points, states=states, conversation_timeout=3600,
                                       fallbacks=[CommandHandler('help', help)])

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
