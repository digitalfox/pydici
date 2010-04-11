# coding:utf-8
"""
Administration form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django.forms import models

from ajax_select.fields import AutoCompleteSelectField

from pydici.leads.models import Lead

class LeadForm(models.ModelForm):
    class Meta:
        model = Lead
    # declare a field and specify the named channel that it uses
    responsible = AutoCompleteSelectField('responsible', required=False)
    salesman = AutoCompleteSelectField('salesman', required=False)
    client = AutoCompleteSelectField('client', required=True)
