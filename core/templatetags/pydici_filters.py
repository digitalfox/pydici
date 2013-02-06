# coding:utf-8
"""
Pydici custom filters
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import re

from django import template
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.utils.translation import ugettext as _
from django.contrib.auth.models import User

from pydici.people.models import Consultant
from pydici.leads.models import Lead
import pydici.settings

register = template.Library()

# *star* word
stared_text = re.compile(r"\*(\w+)\*", re.UNICODE)
# _underlined_ work
underlined_text = re.compile(r"_(\w+)_", re.UNICODE)
# bullet point
bullet_point = re.compile(r"\s*[*-]{1,2}[^*-]", re.UNICODE)


@register.filter
def truncate_by_chars(value, arg):
    """ Truncate words if higher than value and use "..."   """
    try:
        limit = int(arg)
        value = unicode(value)
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
def link_to_consultant(value, arg=None):
    """create a link to consultant if he exists
    @param value: consultant trigramme"""
    try:
        consultant = Consultant.objects.get(trigramme__iexact=value)
        if consultant.name:
            name = consultant.name
        else:
            name = value
        if consultant.subcontractor or arg == "nolink":
            value = escape(name)
        else:
            value = "<a href='%s'>%s</a>" % (reverse("pydici.people.views.consultant_home", args=[consultant.id, ]),
                                        escape(name))
        return mark_safe(value)
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
        url = "<a href='%s#tab-timesheet'>%s</a>" % (reverse("pydici.people.views.consultant_home", args=[c.id, ]),
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
        url = "<a href='%s#tab-staffing'>%s</a>" % (reverse("pydici.people.views.consultant_home", args=[c.id, ]),
                                        escape(_("My staffing")))
        return mark_safe(url)
    except Consultant.DoesNotExist:
        return None


@register.filter
def get_admin_mail(value, arg=None):
    """Config to get admin contact"""
    if pydici.settings.ADMINS:
        return mark_safe("<a href='mailto:%s'>%s</a>" % (pydici.settings.ADMINS[0][1],
                                                         _("Mail to support")))


@register.filter
def pydici_simple_format(value, arg=None):
    """Very simple markup formating.
    Markdown and rst are too much complicated"""
    # format *word* and _word_
    value = stared_text.sub(r"<strong>\1</strong>", value)
    value = underlined_text.sub(r"<em>\1</em>", value)
    result = []
    inList = False  # Flag to indicate we are in a list
    for line in value.split("\n"):
        if bullet_point.match(line):
            if not inList:
                result.append("<ul>")
            result.append(u"<li>%s</li>" % line.strip().lstrip("*").lstrip("-"))
            inList = True
        else:
            if inList:
                result.append("</ul>")
            result.append(line + "\n")
            inList = False

    value = "".join(result)

    # Hook on deal ids
    result = []
    dealIds = [i[0] for i in Lead.objects.exclude(deal_id="").values_list("deal_id")]
    for word in value.split():
        if word in dealIds:
            word = "<a href='%s'>%s</a>" % (Lead.objects.get(deal_id=word).get_absolute_url(), word)
        result.append(word)
    value = " ".join(result)

    return mark_safe(value)
