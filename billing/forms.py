# coding:utf-8
"""
Bill form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django.forms import models
from django.utils.translation import ugettext_lazy as _

from ajax_select.fields import AutoCompleteSelectField

from pydici.billing.models import Bill

class BillForm(models.ModelForm):
    class Meta:
        model = Bill
    # declare a field and specify the named channel that it uses
    lead = AutoCompleteSelectField('lead', required=True, label=_("Lead"))
