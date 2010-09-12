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

from pydici.people.models import Consultant

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

