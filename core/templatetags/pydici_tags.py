# coding:utf-8
"""
Pydici custom tags
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import re

import markdown
from markdown.extensions.sane_lists import SaneListExtension
import bleach

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def call_for_current_subsidiary(context, obj, f_name):
    """Allow calling method on object with current subsidiary as parameter.
    Used for model methods called on templates that do not have access to request and session and cannot be called
    with explicit arguments"""
    subsidiary = context.get("current_subsidiary")
    print(subsidiary)
    f = getattr(obj, f_name)
    if subsidiary:
        return f(subsidiary=subsidiary)
    else:
        return f()