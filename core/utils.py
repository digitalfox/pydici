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
import unicodedata

os.environ['MPLCONFIGDIR'] = '/tmp'  # Needed for matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

from django.template.loader import get_template
from django.template import RequestContext
from django.template.defaultfilters import slugify
from django.http import HttpResponse
from django.core.mail import EmailMultiAlternatives
from django.core import urlresolvers

import pydici.settings

# Graph colors
COLORS = ["#05467A", "#FF9900", "#A7111B", "#DAEBFF", "#FFE32C", "#AAFF86", "#D972FF", "#FF8D8F", "#6BE7FF", "#FF1616"]


def send_lead_mail(lead, request, fromAddr=pydici.settings.LEADS_MAIL_FROM, fromName=""):
    """ Send a mail with lead detailed description.
    @param lead: the lead to send by mail
    @type lead: pydici.leads.lead instance
    @param request: http request of user - used to determine full URL
    @raise exception: if SMTP errors occurs. It is up to the caller to catch that.
    """
    url = pydici.settings.PYDICI_HOST + urlresolvers.reverse("admin:leads_lead_change", args=[lead.id, ]) + "?return_to=" + lead.get_absolute_url()
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
            x = round(x, precision)
            if (int(x) - x) == 0:
                return int(x)
            else:
                return x
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
        if monthDate.weekday() < 5 and monthDate not in holidays:  # Only count working days
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

def nextMonth(month):
    """Compute next month
    @param month: date or datetime object
    @return: date or datetime object (depending on input parameter) of the first day of next month"""
    return (month.replace(day=1) + timedelta(days=40)).replace(day=1)

def previousMonth(month):
    """Compute previoujs month
    @param month: date or datetime object
    @return: date or datetime object (depending on input parameter) of the first day of previous month"""
    return (month.replace(day=1) - timedelta(days=10)).replace(day=1)

def daysOfMonth(month, week=None):
    """
    @param month: datetime object of any day in the month: 
    @param week:week number of week to consider (1 is first etc.). All is none
    @return: list of days (datetime object) for given month"""
    days = []
    day = timedelta(1)
    month = month.replace(day=1)
    tmpDate = month
    nWeek = 1  # Week count
    while tmpDate.month == month.month:
        if week:
            # Only add days if we are in the given week
            if nWeek == week:
                days.append(tmpDate)
            elif nWeek > week:
                # No need to browse remaining days
                break
        else:
            # No week given, we count all days
            days.append(tmpDate)
        if tmpDate.isoweekday() == 7:
            # Sunday, this is next week
            nWeek += 1
                # increment days
        tmpDate += day

    return days


def nextWeek(cDate):
    """
    @return: next monday"""
    day = timedelta(1)
    cDate += day
    while cDate.isoweekday() != 1 and cDate.day != 1: cDate += day
    return cDate

def previousWeek(cDate):
    """
    @return: previous week first day. Weeks are split if across two month"""
    day = timedelta(1)
    while cDate.isoweekday() != 1 and cDate.day != 1:  cDate -= day  # Begining of current week
    cDate -= day  # Go to previous week
    while cDate.isoweekday() != 1 and cDate.day != 1:  cDate -= day  # Begining of current week
    return cDate

def monthWeekNumber(cDate):
    """@return: month week number of given date. First week of month is 1"""
    day = timedelta(1)
    nWeek = 1
    tDate = cDate.replace(day=1)
    while tDate < cDate:
        tDate += day
        if tDate.isoweekday() == 1:
            nWeek += 1
    return nWeek

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

def sampleList(data, maxLength):
    """Sample data list enough to reduce it to maxLength"""
    while (len(data) > maxLength):
        step = int(1 + len(data) / maxLength)
        nData = []
        for i in range(0, len(data), step):
            nData.append(data[i])
        data = nData
    return data


def sanitizeName(name):
    """Sanitize given unicode name to simple ascii name"""
    return unicodedata.normalize('NFKD', name).encode('ascii', 'ignore')


def getLeadDirs(lead):
    """Get documents directories relative to this lead
    @return: clientDir, leadDir, businessDir, inputDir, deliveryDir"""
    clientDir = os.path.join(pydici.settings.DOCUMENT_PROJECT_PATH,
                             pydici.settings.DOCUMENT_PROJECT_CLIENT_DIR.format(name=slugify(lead.client.organisation.company.name), code=lead.client.organisation.company.code))
    if not os.path.exists(clientDir):
        # Look if an alternative path exists with proper client code
        for path in os.listdir(pydici.settings.DOCUMENT_PROJECT_PATH):
            if isinstance(path, str):
                # Corner case, files are not encoded with filesystem encoding but another...
                path = path.decode("utf8", "ignore")
            if path.endswith(u"_%s" % lead.client.organisation.company.code):
                clientDir = os.path.join(pydici.settings.DOCUMENT_PROJECT_PATH, path)
                break

    leadDir = os.path.join(clientDir,
                           pydici.settings.DOCUMENT_PROJECT_LEAD_DIR.format(name=slugify(lead.name), deal_id=lead.deal_id))
    if not os.path.exists(leadDir):
        # Look if an alternative path exists with proper lead code
        for path in os.listdir(clientDir):
            if isinstance(path, str):
            # Corner case, files are not encoded with filesystem encoding but another...
                path = path.decode("utf8", "ignore")
            if path.startswith(lead.deal_id):
                leadDir = os.path.join(clientDir, path)
                break

    businessDir = os.path.join(leadDir,
                               pydici.settings.DOCUMENT_PROJECT_BUSINESS_DIR)
    inputDir = os.path.join(leadDir,
                               pydici.settings.DOCUMENT_PROJECT_INPUT_DIR)
    deliveryDir = os.path.join(leadDir,
                               pydici.settings.DOCUMENT_PROJECT_DELIVERY_DIR)

    return (clientDir, leadDir, businessDir, inputDir, deliveryDir)

def getLeadDocURL(lead):
    """@return: URL to reach this lead base directory"""
    (clientDir, leadDir, businessDir, inputDir, deliveryDir) = getLeadDirs(lead)
    url = pydici.settings.DOCUMENT_PROJECT_URL + leadDir[len(pydici.settings.DOCUMENT_PROJECT_PATH):] + "/"
    return url

def createProjectTree(lead):
    """Create standard document filesystem tree for this lead"""
    for directory in getLeadDirs(lead):
        if not os.path.exists(directory):
            os.mkdir(directory)
