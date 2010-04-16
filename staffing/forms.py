# coding:utf-8
"""
Staffing form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django.forms import models
from django.forms.models import BaseInlineFormSet

from ajax_select.fields import AutoCompleteSelectField


class ConsultantStaffingInlineFormset(BaseInlineFormSet):
    """Custom inline formset used to override fields"""
    def add_fields(self, form, index):
        """that adds the field in, overwriting the previous default field"""
        super(ConsultantStaffingInlineFormset, self).add_fields(form, index)
        form.fields["mission"] = AutoCompleteSelectField('mission', required=True) # Ajax it
        form.fields["mission"].widget.attrs.setdefault("size", 8) # Reduce default size
        form.fields["staffing_date"].widget.attrs.setdefault("size", 10) # Reduce default size
        form.fields["charge"].widget.attrs.setdefault("size", 3) # Reduce default size

class MissionStaffingInlineFormset(BaseInlineFormSet):
    """Custom inline formset used to override fields"""
    def add_fields(self, form, index):
        """that adds the field in, overwriting the previous default field"""
        super(MissionStaffingInlineFormset, self).add_fields(form, index)
        form.fields["consultant"] = AutoCompleteSelectField('consultant', required=True) # Ajax it
        form.fields["consultant"].widget.attrs.setdefault("size", 8) # Reduce default size
        form.fields["staffing_date"].widget.attrs.setdefault("size", 10) # Reduce default size
        form.fields["charge"].widget.attrs.setdefault("size", 3) # Reduce default size
