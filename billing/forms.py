# coding:utf-8
"""
Bill form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.forms import models
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from django.forms.models import BaseInlineFormSet


from crispy_forms.layout import Layout, Div, Column
from crispy_forms.bootstrap import AppendedText, TabHolder, Tab
from crispy_forms.helper import FormHelper
from django_select2 import ModelSelect2Field

from billing.models import ClientBill, SupplierBill, BillDetail
from staffing.models import Mission
from leads.forms import LeadChoices
from expense.forms import ChargeableExpenseMChoices
from crm.forms import SupplierChoices
from staffing.forms import MissionChoices, LeadMissionChoices
from people.forms import ConsultantChoices
from core.forms import PydiciCrispyModelForm


class ClientBillForm(PydiciCrispyModelForm):
    class Meta:
        model = ClientBill
        fields = "__all__"
        widgets = { "lead": LeadChoices,
                    "expenses": ChargeableExpenseMChoices}


    lead = LeadChoices(label=_("Lead"))
    expenses = ChargeableExpenseMChoices(required=False, label=_("Expenses"))


    def __init__(self, *args, **kwargs):
        super(ClientBillForm, self).__init__(*args, **kwargs)
        self.helper.form_tag = False
        self.helper.layout = Layout(Div(TabHolder(Tab(_("Description"),
                                                      Column("lead", "bill_id", "state", css_class="col-md-6"),
                                                      Column("comment", "bill_file", css_class="col-md-6"), ),
                                                  Tab(_("Amounts"),
                                                      Column("amount", "vat", "amount_with_vat", css_class="col-md-6")),
                                                  Tab(_("Dates"), Column("creation_date", "due_date", "payment_date",
                                                                         "previous_year_bill", css_class="col-md-6"), ),
                                                  css_class="row")))


class SupplierBillForm(models.ModelForm):
    lead = LeadChoices(label=_("Lead"))
    expenses = ChargeableExpenseMChoices(required=False, label=_("Expenses"))
    supplier = SupplierChoices(label=_("Supplier"))

    class Meta:
        model = SupplierBill
        fields = "__all__"
        widgets = {"lead": LeadChoices,
                   "expenses": ChargeableExpenseMChoices,
                   "supplier": SupplierChoices}


class BillDetailInlineFormset(BaseInlineFormSet):
    def add_fields(self, form, index):
        super(BillDetailInlineFormset, self).add_fields(form, index)
        form.fields["mission"] = LeadMissionChoices(queryset=Mission.objects.filter(lead=self.instance.lead))
        form.fields["consultant"] = ConsultantChoices(label=_("Consultant"))


class BillDetailFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super(BillDetailFormSetHelper, self).__init__(*args, **kwargs)
        self.form_method = 'post'
        self.form_tag = False
        self.template = 'bootstrap/table_inline_formset.html'
