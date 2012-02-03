# coding:utf-8
"""
Bill form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.forms import models
from django.utils.translation import ugettext_lazy as _

from ajax_select.fields import AutoCompleteSelectField, AutoCompleteSelectMultipleField

from pydici.billing.models import ClientBill


class BillForm(models.ModelForm):
    class Meta:
        model = ClientBill
    # declare a field and specify the named channel that it uses
    lead = AutoCompleteSelectField("lead", required=True, label=_("Lead"))
    expenses = AutoCompleteSelectMultipleField("chargeable_expense", required=False, label=_("Expenses"))
