# coding:utf-8
"""
Bill form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.forms import models

from billing.models import ClientBill, SupplierBill
from leads.forms import LeadChoices
from expense.forms import ChargeableExpenseMChoices
from crm.forms import SupplierChoices


class ClientBillForm(models.ModelForm):
    class Meta:
        model = ClientBill
        fields = "__all__"
        widgets = { "lead": LeadChoices,
                    "expenses": ChargeableExpenseMChoices}


class SupplierBillForm(models.ModelForm):
    class Meta:
        model = SupplierBill
        fields = "__all__"
        widgets = {"lead": LeadChoices,
                   "expenses": ChargeableExpenseMChoices,
                   "supplier": SupplierChoices}

