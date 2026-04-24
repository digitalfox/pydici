# coding:utf-8
"""
Pydici custom tags
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django import template
from django.template.loader import get_template


register = template.Library()

@register.simple_tag(takes_context=True)
def call_for_current_subsidiary(context, obj, f_name):
    """Allow calling method on object with current subsidiary as parameter.
    Used for model methods called on templates that do not have access to request and session and cannot be called
    with explicit arguments"""
    subsidiary = context.get("current_subsidiary")
    f = getattr(obj, f_name)
    if subsidiary:
        return f(subsidiary=subsidiary)
    else:
        return f()

@register.simple_tag(takes_context=True)
def consultant_monthly_staffing(context, consultant, month):
    template = get_template("people/__consultant_monthly_staffing.html")
    staffings, total, available = consultant.monthly_staffing(month)
    if available < 0:
        color = "red"
    else:
        color = "green"
    return template.render({"total": total, "available": available, "color": color})
