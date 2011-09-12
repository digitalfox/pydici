# coding:utf-8
"""
Leads form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.forms import models
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError

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

    def clean_sales(self):
        """Ensure sale amount is defined at lead when commercial proposition has been sent"""
        if self.cleaned_data["sales"] or self.cleaned_data["state"] in ('QUALIF', 'WRITE_OFFER'):
            # Sales is defined or we are in early step, nothing to say
            return self.cleaned_data["sales"]
        else:
            # We can't tolerate that sale amount is not known at this step of the process
            raise ValidationError(_("Sales amount must be defined at this step of the commercial process"))
