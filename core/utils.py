# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import re
import os
from datetime import timedelta

os.environ['MPLCONFIGDIR'] = '/tmp' # Needed for matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

from django.template.loader import get_template
from django.template import RequestContext
from django.http import HttpResponse
from django.core.mail import EmailMultiAlternatives
from django.core import urlresolvers

import pydici.settings

# Graph colors
COLORS = ["#05467A", "#FF9900", "#A7111B", "#DAEBFF", "#FFFF6D", "#AAFF86", "#D972FF", "#FF8D8F"]


def send_lead_mail(lead, request, fromAddr=pydici.settings.LEADS_MAIL_FROM, fromName=""):
    """ Send a mail with lead detailed description.
    @param lead: the lead to send by mail
    @type lead: pydici.leads.lead instance
    @param request: http request of user - used to determine full URL
    @raise exception: if SMTP errors occurs. It is up to the caller to catch that.
    """
    url = pydici.settings.PYDICI_HOST + urlresolvers.reverse("admin:leads_lead_change", args=[lead.id, ])
    subject = u"[AVV] %s : %s" % (lead.client.organisation, lead.name)
    msgText = get_template("leads/lead_mail.txt").render(RequestContext(request, {"obj" : lead,
                                                                                  "lead_url" : url }))
    msgHtml = get_template("leads/lead_mail.html").render(RequestContext(request, {"obj" : lead,
                                                                                   "lead_url" : url }))
    msg = EmailMultiAlternatives(subject, msgText, fromAddr, [pydici.settings.LEADS_MAIL_TO, ])
    msg.attach_alternative(msgHtml, "text/html")
    msg.send()

def capitalize(sentence, keepUpper=False):
    """
    @param sentence: string or unicode
    @param keepUpper: don't change sentence that are all uppercase
    @return:Capitalize each word or sub-word (separated by dash or quote) of the sentence
    """
    if keepUpper and sentence == sentence.upper():
        return sentence

    sentence = sentence.lower()
    result = []
    for sep in (" ", "'", "-"):
        for word in sentence.split(sep):
            if word:
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

def print_png(fig):
    """Return http response with fig rendered as png
    @param fig: fig to render
    @type fig: matplotlib.Figure
    @return: HttpResponse"""
    canvas = FigureCanvas(fig)
    response = HttpResponse(content_type='image/png')
    canvas.print_png(response)
    return response

def sortedValues(data):
    """Sorted value of a dict according to his keys"""
    items = data.items()
    items.sort(key=lambda x: x[0])
    return [x[1] for x in items]
