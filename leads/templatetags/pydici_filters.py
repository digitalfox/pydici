# coding:utf-8
"""
Pydici custom filters
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django import template

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
