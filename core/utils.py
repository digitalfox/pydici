# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from email.Utils import formatdate
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Encoders import encode_7or8bit
from email.Header import Header
import re
from datetime import date, timedelta

from django.template.loader import get_template
from django.template import RequestContext

import pydici.settings

def send_lead_mail(lead, request, fromAddr=pydici.settings.LEADS_MAIL_FROM, fromName=""):
    """ Send a mail with lead detailed description.
    @param lead: the lead to send by mail
    @type lead: pydici.leads.lead instance
    @param request: http request of user - used to determine full URL
    @raise exception: if SMTP errors occurs. It is up to the caller to catch that.
    """

    htmlTemplate = get_template("leads/lead_mail.html")
    textTemplate = get_template("leads/lead_mail.txt")

    msgRoot = MIMEMultipart('related')
    msgRoot.set_charset("UTF-8")
    msgRoot["Date"] = formatdate()
    msgRoot["Subject"] = (u"[AVV] %s : %s" % (lead.client.organisation, lead.name)).encode("UTF-8")
    msgRoot["From"] = "%s <%s>" % (Header(fromName, "UTF-8"), fromAddr)
    msgRoot["To"] = pydici.settings.LEADS_MAIL_TO
    msgRoot.preamble = "This is a multi-part message in MIME format."

    msgAlternative = MIMEMultipart('alternative')
    msgRoot.attach(msgAlternative)

    msgText = MIMEText(textTemplate.render(RequestContext(
                                            request,
                                            {"obj" : lead })).encode("UTF-8"))
    msgText.set_charset("UTF-8")
    encode_7or8bit(msgText)
    msgAlternative.attach(msgText)

    msgText = MIMEText(htmlTemplate.render(RequestContext(
                                            request,
                                            {"obj" : lead })).encode("UTF-8"), 'html')
    msgText.set_charset("UTF-8")
    encode_7or8bit(msgText)
    msgAlternative.attach(msgText)

    # Let exception be thrown to the caller when smtp host is not reachable
    smtpConnection = smtplib.SMTP(pydici.settings.LEADS_MAIL_SMTP)
    smtpConnection.sendmail(pydici.settings.LEADS_MAIL_FROM, pydici.settings.LEADS_MAIL_TO, msgRoot.as_string())
    smtpConnection.quit()

def capitalize(sentence):
    """
    @param sentence: string or unicode
    @return:Capitalize each word or sub-word (separated by dash or quote) of the sentence
    """
    sentence = sentence.lower()
    result = []
    for sep in (" ", "'", "-"):
        for word in sentence.split(sep):
            word = word[0].upper() + word[1:]
            result.append(word)
        sentence = sep.join(result)
        result = []
    return sentence

EXTRA_SPACE = re.compile("[ ]+")
EXTRA_NLINE = re.compile("\n\s*\n+")
def compact_text(text):
    """Compact text by removing extra space and extra lines. BTW, it also squash carriage returns.
    @param text: text to compact
    @return: compacted text"""
    text = text.replace("\r", "")
    text = EXTRA_SPACE.sub(" ", text)
    text = EXTRA_NLINE.sub("\n\n", text)
    return text

def to_int_or_round(x, precision=1):
    """Convert a float to int if decimal part is equal to 0
    else round it with "precision" (default 1) decimal.
    If list/tuple is given, recurse on it.
    Objects other than float are leaved as is.
    @param x: object to be converted"""
    if isinstance(x, (list, tuple)):
        # Recurse
        return map(to_int_or_round, x)
    if isinstance(x, float):
        if (int(x) - x) == 0:
            return int(x)
        else:
            return round(x, precision)
    else:
        # Return as is
        return x

def working_days(monthDate, holidays=[]):
    """Compute the number of working days of a month
    @param monthDate: first day of month datetime.date
    @param holidays: list of days (datetime.date) that are not worked
    @return: number of working days (int)"""
    day = timedelta(1)
    n = 0
    currentMonth = monthDate.month
    while monthDate.month == currentMonth:
        if monthDate.weekday() < 5 and monthDate not in holidays: # Only count working days
            n += 1
        monthDate += day
    return n

def month_days(monthDate):
    """Compute the number of days in a month
    @param monthDate: first day of month datetime.date
    @return: number of days (int)"""
    day = timedelta(1)
    n = 0
    currentMonth = monthDate.month
    while monthDate.month == currentMonth:
        n += 1
        monthDate += day
    return n
