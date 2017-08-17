# coding: utf-8
"""
Admin module for pydici core module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib import admin
from django.utils.encoding import iri_to_uri

from core.models import GroupFeature, Parameter


class ReturnToAppAdmin(admin.ModelAdmin):
    """Generic admin class that enable to return to custom page instead
    of admin default list page after new/change admin form.
    This class is intended to be inherited by all pydici admin classes"""
    actions = None

    def add_view(self, request, form_url='', extra_context=None):
        result = super(ReturnToAppAdmin, self).add_view(request, form_url=form_url, extra_context=extra_context)
        if request.GET.get('return_to', False):
            result['Location'] = iri_to_uri(request.GET['return_to'])
        return result

    def change_view(self, request, object_id, form_url='', extra_context=None):
        result = super(ReturnToAppAdmin, self).change_view(request, object_id, form_url=form_url, extra_context=extra_context)
        if request.GET.get('return_to', False):
            result['Location'] = iri_to_uri(request.GET['return_to'])
        return result


class GroupFeatureAdmin(ReturnToAppAdmin):
    """Admin model for features assigned to groups"""
    list_display = ("group", "feature")
    ordering = ("group", "feature")


class ParameterAdmin(ReturnToAppAdmin):
    """Admin model for pydici parameters"""
    list_display =  ("key", "value", "type", "desc")
    ordering = ("key",)

admin.site.register(GroupFeature, GroupFeatureAdmin)
admin.site.register(Parameter, ParameterAdmin)
