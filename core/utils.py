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
from decimal import Decimal

from django.template.loader import get_template
from django.template.defaultfilters import slugify
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from django.core.cache import cache
from django.db.models import Max, Min
from django.conf import settings

from core.models import GroupFeature, Parameter


# Graph colors
COLORS = ["#1f77b4", "#ff7f0e", "#d62728", "#DAEBFF", "#FFE32C", "#AAFF86", "#D972FF", "#FF8D8F", "#6BE7FF", "#FF1616"]

# Tables 2 css to hide columns on small devices
TABLES2_HIDE_COL_MD = {"td": {"class": "hidden-xs hidden-sm hidden-md"}, "th": {"class": "hidden-xs hidden-sm hidden-md"}}


def send_lead_mail(lead, request, fromAddr=None, fromName=""):
    """ Send a mail with lead detailed description.
    @param lead: the lead to send by mail
    @type lead: leads.lead instance
    @param request: http request of user - used to determine full URL
    @raise exception: if SMTP errors occurs. It is up to the caller to catch that.
    """
    if not fromAddr:
        fromAddr = get_parameter("MAIL_FROM")
    url = get_parameter("HOST") + reverse("leads:lead", args=[lead.id, ]) + "?return_to=" + lead.get_absolute_url()
    subject = "[AVV] %s : %s (%s)" % (lead.client.organisation, lead.name, lead.deal_id)
    msgText = get_template("leads/lead_mail.txt").render(request=request, context={"obj": lead,
                                                                                  "lead_url": url})
    msgHtml = get_template("leads/lead_mail.html").render(request=request, context={"obj": lead,
                                                                                   "lead_url": url})
    msg = EmailMultiAlternatives(subject, msgText, fromAddr, [get_parameter("LEAD_MAIL_TO"), ])
    msg.attach_alternative(msgHtml, "text/html")
    msg.send()


def capitalize(sentence):
    """
    @param sentence: string or unicode
    don't change words that are all uppercase
    @return:Capitalize each word or sub-word (separated by dash or quote) of the sentence
    """
    result = []
    for sep in (" ", "'", "-"):
        for word in sentence.split(sep):
            if word:
                if word.upper() != word:
                    word = word[0].upper() + word[1:]
                result.append(word)
        sentence = sep.join(result)
        result = []
    return sentence


def compact_text(text):
    """Compact text by removing extra space and extra lines. BTW, it also squash carriage returns.
    @param text: text to compact
    @return: compacted text"""
    EXTRA_SPACE = re.compile("[ ]+(?![\*\-])")
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
        return list(map(to_int_or_round, x))
    if isinstance(x, (float, Decimal)):
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


def working_days(monthDate, holidays=None, upToToday=False):
    """Compute the number of working days of a month
    @param monthDate: first day of month datetime.date
    @param holidays: list of days (datetime.date) that are not worked
    @param upToToday: only count days up to (but excluding) today. Only relevant for current month (default is false)
    @return: number of working days (int)"""
    day = timedelta(1)
    today = date.today()
    holidays = holidays or []  # Initialise to empty list here, not in default args to avoid funny things
    n = 0
    if isinstance(monthDate, datetime):
        monthDate = monthDate.date()
    currentMonth = monthDate.month
    while monthDate.month == currentMonth:
        if upToToday and monthDate >= today:
            break
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
    """Compute previous month
    @param month: date or datetime object
    @return: date or datetime object (depending on input parameter) of the first day of previous month"""
    return (month.replace(day=1) - timedelta(days=10)).replace(day=1)


def daysOfMonth(month, week=None):
    """List of days of a month
    @param month: date object of any day in the month
    @param week:week number of week to consider (1 is first etc.). All is none
    @return: list of days (date object) for given month"""
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
    items = list(data.items())
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
    return unicodedata.normalize('NFKD', name)


def getLeadDirs(lead, with_prefix=True):
    """Get documents directories relative to this lead
    @return: client_dir, lead_dir, business_dir, input_dir, delivery_dir"""

    # Compose the path without the prefix, useful for nextcloud for instance
    client_dir = os.path.join(settings.DOCUMENT_PROJECT_CLIENT_DIR.format(name=slugify(lead.client.organisation.company.name),
                                                                          code=lead.client.organisation.company.code))
    if not os.path.exists(client_dir):
        # Look if an alternative path exists with proper client code
        for path in os.listdir(settings.DOCUMENT_PROJECT_PATH):
            if isinstance(path, bytes):
                # Corner case, files are not encoded with filesystem encoding but another...
                path = path.decode("utf8", "ignore")
            if path.endswith("_%s" % lead.client.organisation.company.code):
                client_dir = path
                break

    if with_prefix:
        client_dir = os.path.join(settings.DOCUMENT_PROJECT_PATH, client_dir)

    if not os.path.exists(client_dir):
        os.makedirs(client_dir, exist_ok=True)

    lead_dir = os.path.join(client_dir,
                            settings.DOCUMENT_PROJECT_LEAD_DIR.format(name=slugify(lead.name), deal_id=lead.deal_id))
    if not os.path.exists(lead_dir):
        # Look if an alternative path exists with proper lead code
        for path in os.listdir(client_dir):
            if isinstance(path, bytes):
                # Corner case, files are not encoded with filesystem encoding but another...
                path = path.decode("utf8", "ignore")
            if path.startswith(lead.deal_id):
                lead_dir = os.path.join(client_dir, path)
                break

    business_dir = os.path.join(lead_dir,
                                settings.DOCUMENT_PROJECT_BUSINESS_DIR)
    input_dir = os.path.join(lead_dir,
                             settings.DOCUMENT_PROJECT_INPUT_DIR)
    delivery_dir = os.path.join(lead_dir,
                                settings.DOCUMENT_PROJECT_DELIVERY_DIR)

    return (client_dir, lead_dir, business_dir, input_dir, delivery_dir)


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


def cumulateList(aList):
    """Return a list with cumulative element.
    Ex. [1, 2, 2] => [1, 3, 5]"""
    s = 0
    result = []
    for i in aList:
        s+=i
        result.append(s)
    return result

class GNode(object):
    """Graph node object wrapper"""
    def __init__(self, id_, label, color="#FFF"):
        self.id_ = id_
        self.label = label
        self.color = color

    def data(self):
        data = {"id": self.id_, "value": {"label": self.label, "style": "fill: %s; stroke: #BBB" % self.color}}
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
        return json.dumps([node.data() for node in list(self._nodes.values())])


class GEdge(object):
    """Graph edge object wrapper"""
    def __init__(self, source, target, color="#BBB"):
        self.source = source
        self.target = target
        self.color = color


class GEdges(list):
    """A list of CEdges that can be dumped in json"""
    def dump(self):
        return json.dumps([{"u": edge.source.id_, "v": edge.target.id_, "value": { "style": "stroke: %s;" % edge.color}} for edge in self])


def _get_user_features(user):
    """
    Returns a set of strings representing the features accessible by the user.

    Results are cached to reduce the number of SQL queries.
    """
    #BUG: crash with anonymous user. Should check that user is authenticated first (and before)
    key = "core._get_user_features_" + user.username
    res = cache.get(key)
    if res is None:
        features = [x.feature for x in GroupFeature.objects.filter(group__user=user)]
        res = set(features)
        cache.set(key, res, 60)
    return res


def user_has_feature(user, feature):
    """
    Returns True if `user` has access to `feature`.
    """
    return feature in _get_user_features(user)


def user_has_features(user, features):
    features = set(features)
    return features.issubset(_get_user_features(user))


def get_parameter(key):
    """Get pydici parameter according to key"""
    value = cache.get(Parameter.PARAMETER_CACHE_KEY % key)
    if value is None:
        parameter = Parameter.objects.get(key=key)
        if parameter.type == "FLOAT":
            value = float(parameter.value)
        else:
            value = parameter.value
        cache.set(Parameter.PARAMETER_CACHE_KEY % key, value, 3600*24)
    return value


def get_fiscal_years_from_qs(queryset, date_field_name):
    """Extract fiscal years of items in query set.
    :return list of fiscal years as int"""
    years = [y.year for y in queryset.dates(date_field_name, "year", order="ASC")]
    if not years:
        return []

    boundaries = queryset.aggregate(Min(date_field_name), Max(date_field_name))
    min_boundary = boundaries[date_field_name + "__min"]
    max_boundary = boundaries[date_field_name + "__max"]
    month = get_parameter("FISCAL_YEAR_MONTH")
    if min_boundary.month < month:
        years.insert(0, years[0]-1)  # First date year is part of previous year. Let's add it
    if max_boundary.month < month:
        years.pop()  # Last date year is in fact part of previous fiscal year. Let's remove it

    return [int(y) for y in years]


def get_fiscal_year(d):
    """Extract fiscal year as int from date / datetime object"""
    month = get_parameter("FISCAL_YEAR_MONTH")
    if d.month < month:
        return d.year - 1
    else:
        return d.year


def moving_average(items, n):
    """compute standard moving average of items with a window of n. n first values are None"""
    print(items)
    if n < 2:
        return items
    result = [None] * (n - 1)
    for i, item in enumerate(items[n-1:]):
        x = items[i:i+n]
        if None in x:
            result.append(None)
        else:
            result.append(sum(x)/n)
    return result
