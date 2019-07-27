# coding:utf-8
"""
Pydici custom filters
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import re

import markdown
from markdown.extensions.sane_lists import SaneListExtension
import bleach

from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.utils.translation import ugettext as _
from django.contrib.auth.models import User
from django.core.cache import cache
from django.conf import settings

from people.models import Consultant
from leads.models import Lead

register = template.Library()

regex_template = r"""
    (?P<before>\W|^)
    {fence}
    (?P<content>([^{fence}]|{fence}\w)+)
    {fence}
    (?P<after>\W|^)
    """
# *star* text
stared_text = re.compile(
    regex_template.format(fence=r'\*'),
    re.UNICODE | re.VERBOSE)
# _underlined_ text
underlined_text = re.compile(
    regex_template.format(fence='_'),
    re.UNICODE | re.VERBOSE)
# bullet point
bullet_point = re.compile(r"\s*[*-]{1,2}[^*-]", re.UNICODE)


@register.filter
def truncate_by_chars(value, arg):
    """ Truncate words if higher than value and use "..."   """
    try:
        limit = int(arg)
        value = str(value)
    except ValueError:
        return value
    if len(value) >= limit:
        return value[:limit - 3] + "..."
    else:
        return value


@register.filter
def split(value, arg):
    """Split a string on "arg" and return a list"""
    return value.split(arg)


@register.filter
def to_float(value, arg=None):
    """Coerce value to float. Return unchanged value if cast fails"""
    try:
        return float(value)
    except ValueError:
        return value


@register.filter
def link_to_consultant(value, arg=None):
    """create a link to consultant if he exists
    @param value: consultant trigramme"""
    result = cache.get("link_to_consultant_%s" % value)
    if result:
        return result
    try:
        consultant = Consultant.objects.get(trigramme__iexact=value)
        if consultant.name:
            name = consultant.name
        else:
            name = value
        if consultant.subcontractor or arg == "nolink":
            result = escape(name)
        else:
            result = "<a href='%s'>%s</a>" % (reverse("people:consultant_home", args=[consultant.trigramme, ]),
                                        escape(name))
        result = mark_safe(result)
        cache.set("link_to_consultant_%s" % value, result, 180)
        return mark_safe(result)
    except Consultant.DoesNotExist:
        try:
            user = User.objects.get(username=value)
            return "%s %s" % (user.first_name, user.last_name)
        except User.DoesNotExist:
            # User must exists if logged... anyways, be safe.
            return value


@register.filter
def link_to_timesheet(value, arg=None):
    """create a link to consultant timesheet if he exists
    @param value: consultant trigramme"""
    try:
        c = Consultant.objects.get(trigramme__iexact=value)
        url = "<a href='%s#tab-timesheet'>%s</a>" % (reverse("people:consultant_home", args=[c.trigramme, ]),
                                        escape(_("My timesheet")))
        return mark_safe(url)
    except Consultant.DoesNotExist:
        return None


@register.filter
def link_to_staffing(value, arg=None):
    """create a link to consultant forecast staffing if he exists
    @param arg: consultant trigramme"""
    try:
        c = Consultant.objects.get(trigramme__iexact=value)
        url = "<a href='%s#tab-staffing'>%s</a>" % (reverse("people:consultant_home", args=[c.trigramme, ]),
                                        escape(_("My staffing")))
        return mark_safe(url)
    except Consultant.DoesNotExist:
        return None


@register.filter
def get_admin_mail(value, arg=None):
    """Config to get admin contact"""
    if settings.ADMINS:
        return mark_safe("<a href='mailto:%s'>%s</a>" % (settings.ADMINS[0][1],
                                                         _("Mail to support")))


@register.filter
def pydici_simple_format(value, arg=None):
    """Very simple markup formating based on markdown and custom links"""
    dealIds = [i[0] for i in Lead.objects.exclude(deal_id="").values_list("deal_id")]
    trigrammes = [i[0] for i in Consultant.objects.values_list("trigramme")]

    #TODO: this may not scale with thousands of leads. It may be splitted in shunk on day.
    for dealId in set(re.findall(r"\b(%s)\b" % "|".join(dealIds), value)):
        value = re.sub(r"\b%s\b" % dealId,
                       "<a href='%s'>%s</a>" % (Lead.objects.get(deal_id=dealId).get_absolute_url(), dealId),
                       value)

    for trigramme in set(re.findall(r"\b(%s)\b" % "|".join(trigrammes), value)):
        value = re.sub(r"\b%s\b" % trigramme,
                       "<a href=%s>%s</a>" % (Consultant.objects.get(trigramme=trigramme).get_absolute_url(), trigramme),
                       value)

    # Authorized tags for markdown (thanks https://github.com/yourcelf/bleach-whitelist/blob/master/bleach_whitelist/bleach_whitelist.py)
    markdown_tags = ["h1", "h2", "h3", "h4", "h5", "h6", "b", "i", "strong", "em", "tt", "p", "br",
                     "span", "div", "blockquote", "code", "hr","ul", "ol", "li", "dd", "dt", "img","a"]
    markdown_attrs = {"img": ["src", "alt", "title"],  "a": ["href", "alt", "title"] }
    value = bleach.clean(markdown.markdown(value, tab_length=2, extensions=[SaneListExtension(),]), tags=markdown_tags, attributes=markdown_attrs)

    return mark_safe(value)
