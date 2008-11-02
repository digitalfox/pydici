# coding: utf-8

""" Helper module that factorize some code that would not be
    appropriate to live in models or view"""

from email.Utils import formatdate
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Encoders import encode_7or8bit

from django.template.loader import get_template
from django.template import Context

import pydici.settings

def send_lead_mail(lead):
    """ Send a mail with lead detailed description.
    @param lead: the lead to send by mail
    @type lead: pydici.leads.lead instance
    @raise exception: if SMTP errors occurs. It is up to the caller to catch that.
    """

    htmlTemplate=get_template("leads/lead_mail.html")
    textTemplate=get_template("leads/lead_mail.txt")

    msgRoot = MIMEMultipart('related')
    msgRoot.set_charset("UTF-8")
    msgRoot["Date"]=formatdate()
    msgRoot["Subject"]=(u"[AVV] %s : %s" % (lead.client.organisation, lead.name)).encode("UTF-8")
    msgRoot["From"]=pydici.settings.LEADS_MAIL_FROM
    msgRoot["To"]=pydici.settings.LEADS_MAIL_TO
    msgRoot.preamble="This is a multi-part message in MIME format."

    msgAlternative = MIMEMultipart('alternative')
    msgRoot.attach(msgAlternative)

    msgText = MIMEText(textTemplate.render(Context({"lead" : lead, "link_root": pydici.settings.LEADS_MAIL_LINK_ROOT })).encode("UTF-8"))
    msgText.set_charset("UTF-8")
    encode_7or8bit(msgText)
    msgAlternative.attach(msgText)

    msgText = MIMEText(htmlTemplate.render(Context({"lead" : lead, "link_root": pydici.settings.LEADS_MAIL_LINK_ROOT })).encode("UTF-8"), 'html')
    msgText.set_charset("UTF-8")
    encode_7or8bit(msgText)
    msgAlternative.attach(msgText)

    # Let exception be thrown to the caller when smtp host is not reachable
    smtpConnection = smtplib.SMTP(pydici.settings.LEADS_MAIL_SMTP)
    smtpConnection.sendmail(pydici.settings.LEADS_MAIL_FROM, pydici.settings.LEADS_MAIL_TO, msgRoot.as_string())
    smtpConnection.quit()
