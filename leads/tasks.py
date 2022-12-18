# coding: utf-8

"""
Module that handle asynchronous tasks
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from datetime import datetime, timedelta

from django.conf import settings
from django.urls import reverse
from django.utils.translation import  gettext
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template

from celery import shared_task
from leads.learn import compute_leads_state, compute_leads_tags, compute_lead_similarity
from core.utils import get_parameter
from leads.models import Lead

if settings.TELEGRAM_IS_ENABLED:
    import telegram


@shared_task
def learning_warmup():
    """Warmup cache while people are sleeping to avoid punishing the first user of the day"""
    compute_leads_state.delay(relearn=True)
    compute_leads_tags.delay(relearn=True)
    compute_lead_similarity.delay(relearn=True)

@shared_task
def lead_notify(lead_id, send_mail=False, from_addr=None, from_name=None, created=False, state_changed=False):
    """Notify (mail, telegram) about lead creation or status update"""
    lead = Lead.objects.get(id=lead_id)
    if send_mail:
        url = get_parameter("HOST") + reverse("leads:lead", args=[lead.id, ]) + "?return_to=" + lead.get_absolute_url()
        subject = "[AVV] %s : %s (%s)" % (lead.client.organisation, lead.name, lead.deal_id)
        msgText = get_template("leads/lead_mail.txt").render(context={"obj": lead, "lead_url": url})
        msgHtml = get_template("leads/lead_mail.html").render(context={"obj": lead, "lead_url": url})
        msg = EmailMultiAlternatives(subject, msgText, from_addr, [get_parameter("LEAD_MAIL_TO"), ])
        msg.attach_alternative(msgHtml, "text/html")
        msg.send()

    if settings.TELEGRAM_IS_ENABLED:
        bot = telegram.bot.Bot(token=settings.TELEGRAM_TOKEN)
        sticker = None
        url = get_parameter("HOST") + reverse("leads:detail", args=[lead.id, ])
        if created:
            msg = gettext("New Lead !\n%(lead)s\n%(url)s") % {"lead": lead, "url":url }
            sticker = settings.TELEGRAM_STICKERS.get("happy")
            chat_group = "new_leads"
        elif state_changed:
            # Only notify when lead state changed to avoid useless spam
            change = ""
            for log in lead.history.filter(timestamp__gt=datetime.now()-timedelta(1/24)):
                change += f"{log.changes_str} ({log.actor})\n"
            msg = gettext("Lead %(lead)s has been updated\n%(url)s\n%(change)s") % {"lead": lead, "url": url, "change": change}
            if lead.state == "WON":
                sticker = settings.TELEGRAM_STICKERS.get("happy")
            elif lead.state in ("LOST", "FORGIVEN"):
                sticker = settings.TELEGRAM_STICKERS.get("sad")
            chat_group = "leads_update"
        else:
            # No notification
            chat_group = msg = ""

        for chat_id in settings.TELEGRAM_CHAT.get(chat_group, []):
            bot.sendMessage(chat_id=chat_id, text=msg, disable_web_page_preview=True)
            if sticker:
                bot.sendSticker(chat_id=chat_id, sticker=sticker)

