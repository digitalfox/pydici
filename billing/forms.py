# coding:utf-8
"""
Bill form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.forms import models
from django.utils.translation import ugettext_lazy as _

from billing.models import ClientBill, SupplierBill
#from leads.forms import LeadChoices
#from expense.forms import ChargeableExpenseMChoices
#from crm.forms import SupplierChoices


class BillForm(models.ModelForm):
    """Abstract Bill Form. Need to be subclassed with, at least, the Meta inner class to define related model"""
 #   lead = LeadChoices(label=_("Lead"))
    #expenses = ChargeableExpenseMChoices(required=False, label=_("Expenses"))


class ClientBillForm(BillForm):
    class Meta:
        model = ClientBill
        fields = "__all__"


class SupplierBillForm(BillForm):
  #  supplier = SupplierChoices(label=_("Supplier"))

    class Meta:
        model = SupplierBill
        fields = "__all__"
