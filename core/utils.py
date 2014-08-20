# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import re
import os
from datetime import timedelta, date, datetime
import unicodedata
from functools import wraps
import json


from django.template.loader import get_template
from django.template import RequestContext
from django.template.defaultfilters import slugify
from django.core.mail import EmailMultiAlternatives
from django.core import urlresolvers
from django.core.cache import cache

import pydici.settings

# Graph colors
COLORS = ["#05467A", "#FF9900", "#A7111B", "#DAEBFF", "#FFE32C", "#AAFF86", "#D972FF", "#FF8D8F", "#6BE7FF", "#FF1616"]

# Tables 2 css to hide columns on small devices
TABLES2_HIDE_COL_MD = {"td": {"class": "hidden-xs hidden-sm hidden-md"}, "th": {"class": "hidden-xs hidden-sm hidden-md"}}


def send_lead_mail(lead, request, fromAddr=pydici.settings.LEADS_MAIL_FROM, fromName=""):
    """ Send a mail with lead detailed description.
    @param lead: the lead to send by mail
    @type lead: leads.lead instance
    @param request: http request of user - used to determine full URL
    @raise exception: if SMTP errors occurs. It is up to the caller to catch that.
    """
    url = pydici.settings.PYDICI_HOST + urlresolvers.reverse("leads.views.lead", args=[lead.id, ]) + "?return_to=" + lead.get_absolute_url()
    subject = u"[AVV] %s : %s (%s)" % (lead.client.organisation, lead.name, lead.deal_id)
    msgText = get_template("leads/lead_mail.txt").render(RequestContext(request, {"obj": lead,
                                                                                  "lead_url": url}))
    msgHtml = get_template("leads/lead_mail.html").render(RequestContext(request, {"obj": lead,
                                                                                   "lead_url": url}))
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


def compact_text(text):
    """Compact text by removing extra space and extra lines. BTW, it also squash carriage returns.
    @param text: text to compact
    @return: compacted text"""
    EXTRA_SPACE = re.compile("[ ]+")
    EXTRA_NLINE = re.compile("\n\s*\n+")
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


def working_days(monthDate, holidays=[], upToToday=False):
    """Compute the number of working days of a month
    @param monthDate: first day of month datetime.date
    @param holidays: list of days (datetime.date) that are not worked
    @param upToToday: only count days up to today. Only relevant for current month (default is false)
    @return: number of working days (int)"""
    day = timedelta(1)
    today = date.today()
    n = 0
    if isinstance(monthDate, datetime):
        monthDate = monthDate.date()
    currentMonth = monthDate.month
    while monthDate.month == currentMonth:
        if monthDate.weekday() < 5 and monthDate not in holidays:  # Only count working days
            n += 1
        monthDate += day
        if upToToday and monthDate > today:
            break
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
    """Compute previous month
    @param month: date or datetime object
    @return: date or datetime object (depending on input parameter) of the first day of previous month"""
    return (month.replace(day=1) - timedelta(days=10)).replace(day=1)


def daysOfMonth(month, week=None):
    """List of days of a month
    @param month: datetime object of any day in the month
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
    while cDate.isoweekday() != 1 and cDate.day != 1:
        cDate += day
    return cDate


def previousWeek(cDate):
    """
    @return: previous week first day. Weeks are split if across two month"""
    day = timedelta(1)
    while cDate.isoweekday() != 1 and cDate.day != 1:
        cDate -= day  # Begining of current week
    cDate -= day  # Go to previous week
    while cDate.isoweekday() != 1 and cDate.day != 1:
        cDate -= day  # Begining of current week
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

    if not os.path.exists(clientDir):
        os.mkdir(clientDir)

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


def createProjectTree(lead):
    """Create standard document filesystem tree for this lead"""
    for directory in getLeadDirs(lead):
        if not os.path.exists(directory):
            os.mkdir(directory)


def disable_for_loaddata(signal_handler):
    """Decorator that turns off signal handlers when loading fixture data.
    Thanks to garnertb: http://stackoverflow.com/questions/15624817/have-loaddata-ignore-or-disable-post-save-signals"""
    @wraps(signal_handler)
    def wrapper(*args, **kwargs):
        if kwargs['raw']:
            return
        signal_handler(*args, **kwargs)
    return wrapper


def cacheable(cache_key, timeout=3600):
    """Decorator to simplify model level method caching.
    Adapted from http://djangosnippets.org/snippets/1130/"""
    def paramed_decorator(func):
        def decorated(self):
            key = cache_key % self.__dict__
            res = cache.get(key)
            if res is None:
                res = func(self)
                cache.set(key, res, timeout)
            return res
        decorated.__doc__ = func.__doc__
        decorated.__dict__ = func.__dict__
        return decorated
    return paramed_decorator


def convertDictKeyToDateTime(data):
    """Convert dict key from unicode string with %Y-%m-%d %H:%M:%S format, to datetime.
    This is used to convert dict from queryset for sqlite3 that don't support properly date trunc functions
    If data is empty or if key is already, datetime, return as is"""
    if data and isinstance(data.keys()[0], unicode):
        return dict((datetime.strptime(k, "%Y-%m-%d %H:%M:%S"), v) for k, v in data.items())
    else:
        return data


class GNode(object):
    """Graph node object wrapper"""
    def __init__(self, id_, label):
        self.id_ = id_
        self.label = label

    def data(self):
        data = {"id": self.id_, "value": {"label": self.label}}
        return data

    def __hash__(self):
        return hash(self.id_)


class GNodes(object):
    """A set of GNodes that can be dumped in json"""

    def __init__(self):
        self._nodes = {}

    def add(self, node):
        if node.id_ not in self._nodes:
            self._nodes[node.id_] = node

    def dump(self):
        return json.dumps([node.data() for node in self._nodes.values()])


class GEdge(object):
    """Graph edge object wrapper"""
    def __init__(self, source, target):
        self.source = source
        self.target = target


class GEdges(list):
    """A list of CEdges that can be dumped in json"""
    def dump(self):
        return json.dumps([{"u": edge.source.id_, "v": edge.target.id_} for edge in self])
