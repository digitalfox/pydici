#!/usr/bin/env python
# coding: utf-8

"""
Telegram bot for timesheet input

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import sys
import os
from os.path import abspath, join, dirname, pardir
import logging
from datetime import date

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO,
)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, ConversationHandler, CallbackContext

# # Setup django envt & django imports
PYDICI_DIR = abspath(join(dirname(__file__), pardir))
os.environ['DJANGO_SETTINGS_MODULE'] = "pydici.settings"

sys.path.append(PYDICI_DIR)  # Add project path to python path

# Ensure we are in the good current working directory (pydici home)
os.chdir(PYDICI_DIR)

# Django imports
from django.core.wsgi import get_wsgi_application
from django.db.models import Sum

# Init and model loading
application = get_wsgi_application()

# Pydici imports
from people.models import Consultant
from staffing.models import Mission, Timesheet, Holiday

logger = logging.getLogger(__name__)

# Stages
MISSION_SELECT, MISSION_TIMESHEET = range(2)

NONPROD_BUTTON = InlineKeyboardButton("non production mission ?", callback_data="NONPROD")


def mission_keyboard(consultant, nature):
    keyboard = []
    for mission in consultant.forecasted_missions():
        if mission.nature == nature:
            keyboard.append([InlineKeyboardButton(mission.short_name(), callback_data=str(mission.id)),])
    return keyboard


def remaining_time_to_declare(context):
    consultant = context.user_data["consultant"]
    today = date.today()
    holidays = Holiday.objects.all()
    if today.weekday() < 15 and today not in holidays:
        declared = Timesheet.objects.filter(consultant=consultant, working_date=today).aggregate(Sum("charge"))[
                       "charge__sum"] or 0
        return 1 - declared - sum(context.user_data["timesheet"].values())
    else:
        return 0


def start(update, context):
    """Start timesheet session when user type /start"""
    user = update.message.from_user
    try:
        consultant = Consultant.objects.get(telegram_alias="%s" % user.name.lstrip("@"), active=True)
    except Consultant.DoesNotExist:
        update.message.reply_text("sorry, i don't know you")
        return ConversationHandler.END

    context.user_data["consultant"] = consultant
    context.user_data["mission_nature"] = "PROD"
    context.user_data["timesheet"] = {}

    keyboard = mission_keyboard(consultant, "PROD")
    keyboard.append([NONPROD_BUTTON])

    update.message.reply_text("On what did you work today ?", reply_markup=InlineKeyboardMarkup(keyboard))

    return MISSION_SELECT


def mission_timesheet(update, context):
    """Declare timesheet for given mission"""
    query = update.callback_query
    query.answer()
    mission = Mission.objects.get(id=int(query.data))
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
    query.edit_message_text(
        text="how much did you work on %s ? (%s is remaining for today)" % (mission.short_name(), remaining_time_to_declare(context)),
        reply_markup=InlineKeyboardMarkup(keyboard))
    return MISSION_TIMESHEET


def end(update, context):
    """Returns `ConversationHandler.END`, which tells the  ConversationHandler that the conversation is over"""
    query = update.callback_query
    query.answer()
    msg = "You timesheet was updated:\n"
    msg += "\n - ".join(["%s : %s" % (m.short_name(), c) for m, c in context.user_data["timesheet"].items()])
    total = sum(context.user_data["timesheet"].values())
    if total > 1:
        msg += "\n\nWhat a day, %s declared. Time to get some rest!" % total
    elif total < 1:
        msg += "\n\nOnly %s today. Don't you forget to declare something ?" % total
    query.edit_message_text(text=msg)
    return ConversationHandler.END


def select_mission(update, context):
    """Select mission to update"""
    query = update.callback_query
    query.answer()
    consultant = context.user_data["consultant"]
    if query.data == "NONPROD":
        context.user_data["mission_nature"] = "NONPROD"
    else:
        mission = context.user_data["mission"]
        context.user_data["timesheet"][mission] = float(query.data)

    keyboard = mission_keyboard(consultant, context.user_data["mission_nature"])

    if context.user_data["mission_nature"] == "PROD":
        keyboard.append([NONPROD_BUTTON])
    else:
        keyboard.append([InlineKeyboardButton("That's all for today !", callback_data="END")])

    query.edit_message_text(text="On which other mission did you work today ?", reply_markup=InlineKeyboardMarkup(keyboard))
    return MISSION_SELECT


def main():
    updater = Updater(os.environ["PYDICI_TOKEN"], use_context=True)
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MISSION_SELECT: [
                CallbackQueryHandler(select_mission, pattern="NONPROD"),
                CallbackQueryHandler(end, pattern="END"),
                CallbackQueryHandler(mission_timesheet),
            ],
            MISSION_TIMESHEET: [
                CallbackQueryHandler(select_mission),
            ],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    # Add ConversationHandler to dispatcher
    dispatcher.add_handler(conv_handler)

    # Start the Bot
    updater.start_polling()

    # Run the bot until Ctrl-C or SIGINT,SIGTERM or SIGABRT.
    updater.idle()


if __name__ == '__main__':
    main()
