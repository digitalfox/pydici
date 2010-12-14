# coding:utf-8
"""
Leads form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django.forms import models
from django.utils.translation import ugettext_lazy as _

from ajax_select.fields import AutoCompleteSelectField

from pydici.leads.models import Lead

class LeadForm(models.ModelForm):
    class Meta:
        model = Lead
    # declare a field and specify the named channel that it uses
    responsible = AutoCompleteSelectField('consultant', required=False, label=_("Responsible"))
    salesman = AutoCompleteSelectField('salesman', required=False, label=_("Salesman"))
    business_broker = AutoCompleteSelectField('business_broker', required=False, label=_("Business broker"))
    paying_authority = AutoCompleteSelectField('business_broker', required=False, label=_("Paying authority"))
    client = AutoCompleteSelectField('client', required=True, label=_("Client"))
