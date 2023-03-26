# coding: utf-8
"""
Conversational consultant timesheet declaration with telegram bot

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, CallbackQueryHandler, CommandHandler

from django.db import transaction
from django.utils.translation import gettext as _

from staffing.models import Mission, Timesheet
from staffing.utils import check_timesheet_validity

from bot.utils import check_user_is_declared, db_sync_to_async

# States
MISSION_SELECT = "MISSION_SELECT"
MISSION_TIMESHEET = "MISSION_TIMESHEET"

# Buttons
NONPROD_BUTTON = InlineKeyboardButton(_("non productive mission?"), callback_data="NONPROD")
END_TIMESHEET_BUTTON = InlineKeyboardButton(_("That's all for today !"), callback_data="END")


@db_sync_to_async
def mission_keyboard(consultant, nature):
    keyboard = []
    for mission in consultant.forecasted_missions():
        if mission.nature == nature:
            keyboard.append([InlineKeyboardButton(mission.short_name(), callback_data=str(mission.id)),])
    return keyboard


async def mission_timesheet(update, context):
    """Declare timesheet for given mission"""
    query = update.callback_query
    await query.answer()
    mission = await db_sync_to_async(Mission.objects.get)(id=int(query.data))
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
        text=_("how much did you work on %(mission)s ? (%(time)s is remaining for today)") % {"mission": await db_sync_to_async(mission.short_name)(),
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

@db_sync_to_async
def update_timesheet(context):
    """Update consultant timesheet and return summary message"""
    consultant = context.user_data["consultant"]
    missions = []
    with transaction.atomic():
        sid = transaction.savepoint()
        Timesheet.objects.filter(consultant=consultant, working_date=date.today()).delete()
        for mission, charge in context.user_data["timesheet"].items():
            Timesheet.objects.create(mission=mission, consultant=consultant,
                                     charge=charge, working_date=date.today())
            missions.append(mission)
        error = check_timesheet_validity(missions, consultant, date.today().replace(day=1))
        if error:
            transaction.savepoint_rollback(sid)
            msg = error
        else:  # No violations, we can commit
            transaction.savepoint_commit(sid)
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


def declare_time_states():
    return { MISSION_SELECT: [
                    CallbackQueryHandler(select_mission, pattern="NONPROD"),
                    CallbackQueryHandler(end_timesheet, pattern="END"),
                    CallbackQueryHandler(mission_timesheet),
                ],
                MISSION_TIMESHEET: [
                    CallbackQueryHandler(select_mission),
                ]}


def declare_time_entry_points():
    return CommandHandler('time', declare_time),