# coding:utf-8
"""
Pydici custom filters
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""


from django import template
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.utils.translation import ugettext as _
from pydici.people.models import Consultant
import pydici.settings

register = template.Library()

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
    @param arg: consultant trigramme"""
    try:
        c = Consultant.objects.get(trigramme__iexact=value)
        if c.name:
            name = c.name
        else:
            name = value
        url = "<a href='%s'>%s</a>" % (reverse("pydici.people.views.consultant_detail", args=[c.id, ]),
                                        escape(name))
        return mark_safe(url)
    except Consultant.DoesNotExist:
        return value

@register.filter
def link_to_timesheet(value, arg=None):
    """create a link to consultant timesheet if he exists
    @param arg: consultant trigramme"""
    try:
        c = Consultant.objects.get(trigramme__iexact=value)
        url = "<a href='%s'>%s</a>" % (reverse("pydici.staffing.views.consultant_timesheet", args=[c.id, ]),
                                        escape(_("My timesheet")))
        return mark_safe(url)
    except Consultant.DoesNotExist:
        return value

@register.filter
def link_to_staffing(value, arg=None):
    """create a link to consultant forecast staffing if he exists
    @param arg: consultant trigramme"""
    try:
        c = Consultant.objects.get(trigramme__iexact=value)
        url = "<a href='%s'>%s</a>" % (reverse("pydici.staffing.views.consultant_staffing", args=[c.id, ]),
                                        escape(_("My staffing")))
        return mark_safe(url)
    except Consultant.DoesNotExist:
        return value

@register.filter
def get_admin_mail(value, arg=None):
    # Config to get admin conctat
    if pydici.settings.ADMINS:
        return mark_safe("<a href='mailto:%s'>%s</a>" % (pydici.settings.ADMINS[0][1],
                                                         _("Mail to support")))

