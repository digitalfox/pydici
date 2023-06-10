# coding: utf-8

"""
Module that handle asynchronous tasks
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from datetime import datetime, timedelta
import smtplib
import asyncio

from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext, pgettext
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template

from celery import shared_task
from taggit.models import Tag

from leads.learn import compute_leads_state, compute_leads_tags, compute_lead_similarity
from core.utils import get_parameter, audit_log_is_real_change, getLeadDirs
from leads.models import Lead

if settings.TELEGRAM_IS_ENABLED:
    from telegram.ext import Application as TelegramApplication
    from telegram.error import TelegramError

@shared_task
def learning_warmup():
    """Warmup cache while people are sleeping to avoid punishing the first user of the day"""
    compute_leads_state.delay(relearn=True)
    compute_leads_tags.delay(relearn=True)
    compute_lead_similarity.delay(relearn=True)

@shared_task(bind=True)
def lead_mail_notify(self, lead_id, from_addr=None, from_name=None):
    """Notify (mail, telegram) about lead creation or status update"""
    lead = Lead.objects.get(id=lead_id)

    if not from_addr:
        pass
    if from_name:
       from_addr = f"{from_name} <{from_addr}>"

    url = get_parameter("HOST") + reverse("leads:lead", args=[lead.id, ]) + "?return_to=" + lead.get_absolute_url()
    subject = "[AVV] %s : %s (%s)" % (lead.client.organisation, lead.name, lead.deal_id)
    msgText = get_template("leads/lead_mail.txt").render(context={"obj": lead, "lead_url": url})
    msgHtml = get_template("leads/lead_mail.html").render(context={"obj": lead, "lead_url": url})
    msg = EmailMultiAlternatives(subject, msgText, from_addr, [get_parameter("LEAD_MAIL_TO"), ])
    msg.attach_alternative(msgHtml, "text/html")
    try:
        msg.send()
    except smtplib.SMTPException as e:
        raise self.retry(exc=e)


@shared_task(bind=True)
def lead_telegram_notify(self, lead_id, created=False, state_changed=False):
    lead = Lead.objects.get(id=lead_id)
    if not settings.TELEGRAM_IS_ENABLED:
        return
    try:
        application = TelegramApplication.builder().token(settings.TELEGRAM_TOKEN).http_version("1.1").get_updates_http_version("1.1").build()
        bot = application.bot
        sticker = None
        url = get_parameter("HOST") + reverse("leads:detail", args=[lead.id, ])
        chat_consultants = []  # List of individual consultant to notify
        if created:
            msg = gettext("New Lead !\n%(lead)s\n%(url)s") % {"lead": lead, "url":url }
            sticker = settings.TELEGRAM_STICKERS.get("happy")
            chat_group = "new_leads"
        elif state_changed:
            # Only notify when lead state changed to avoid useless spam
            change = ""
            for log in lead.history.filter(timestamp__gt=datetime.now()-timedelta(1/24)):
                for key, value in log.changes_display_dict.items():
                    if audit_log_is_real_change(value) and len(value) == 2:
                        change += f"{key}: {value[0]} → {value[1]} ({log.actor})\n".replace("None", "-")
                for key, value in log.changes_dict.items(): # Second loop for m2m
                    if len(value) == 3: # m2m changes
                        change += f"{key}: {pgettext('noun', value['operation'])} {', '.join(value['objects'])}\n"
            msg = gettext("Lead %(lead)s for %(subsidiary) has been updated\n%(url)s\n%(change)s") % {"lead": lead,
                                                                                                      "subsidiary": lead.subsidiary,
                                                                                                      "url": url,
                                                                                                      "change": change}
            if lead.state == "WON":
                sticker = settings.TELEGRAM_STICKERS.get("happy")
            elif lead.state in ("LOST", "FORGIVEN"):
                sticker = settings.TELEGRAM_STICKERS.get("sad")
            chat_group = "leads_update"
            if lead.responsible.profil.level < settings.TELEGRAM_CHAT_MANAGER_LEVEL and lead.responsible.telegram_id:
                chat_consultants.append(lead.responsible.telegram_id)
            for consultant in lead.staffing.all():
                if consultant.profil.level < settings.TELEGRAM_CHAT_MANAGER_LEVEL and consultant.telegram_id:
                    chat_consultants.append(consultant.telegram_id)
        else:
            # No notification
            chat_group = msg = ""

        loop = asyncio.new_event_loop()
        for chat_id in set(settings.TELEGRAM_CHAT.get(chat_group, []) + chat_consultants):
            loop.run_until_complete(bot.sendMessage(chat_id=chat_id, text=msg, disable_web_page_preview=True))
            if sticker:
                loop.run_until_complete(bot.sendSticker(chat_id=chat_id, sticker=sticker))
    except TelegramError as e:
        raise self.retry(exc=e)
