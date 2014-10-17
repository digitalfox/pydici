# coding:utf-8
"""
Bill form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.forms import models, ModelForm
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.forms.models import BaseInlineFormSet
from django.forms.util import ValidationError


from crispy_forms.layout import Layout, Div, Column
from crispy_forms.bootstrap import TabHolder, Tab
from crispy_forms.helper import FormHelper

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

    def clean_amount(self):
        if self.cleaned_data["amount"] or self.data["state"] == "0_DRAFT":
            # Amount is defined or we are in early step, nothing to say
            return self.cleaned_data["amount"]
        else:
            # Amount must be defined
            raise ValidationError(_("Bill amount must be computed from bill detail or defined manually"))

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
        form.fields["consultant"] = ConsultantChoices(label=_("Consultant"), required=False)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        staffings = []
        for form in self.forms:
            if form.cleaned_data.get("detail_type", "") != "TIME_SPENT_MISSION":
                continue
            staffing = [form.cleaned_data['mission'].id, form.cleaned_data['month'].toordinal(), form.cleaned_data["consultant"].id]
            if staffing in staffings:
                raise ValidationError(_("Cannot declare twice the same consultant for the same mission on a given month"))
            staffings.append(staffing)



class BillDetailFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super(BillDetailFormSetHelper, self).__init__(*args, **kwargs)
        self.form_method = 'post'
        self.form_tag = False
        self.template = 'bootstrap/table_inline_formset.html'

class BillDetailForm(ModelForm):
    def clean_consultant(self):
        if not self.cleaned_data["consultant"] and self.cleaned_data["detail_type"] == "TIME_SPENT_MISSION":
            raise ValidationError(_("Consultant must be defined for time spent mission"))
        return self.cleaned_data["consultant"]

    def clean_month(self):
        if not self.cleaned_data["month"] and self.cleaned_data["detail_type"] == "TIME_SPENT_MISSION":
            raise ValidationError(_("Month must be defined for time spent mission"))
        return self.cleaned_data["month"]


    def clean(self):
        mission = self.cleaned_data.get("mission", False)
        if mission:
            invalid_type = ValidationError(ugettext("Type is not consistent with mission %s billing mode (%s)") % (mission.mission_id(), mission.get_billing_mode_display()))
            if mission.billing_mode == "FIXED_PRICE" and  self.cleaned_data["detail_type"] != "FIXED_PRICE_MISSION":
                raise invalid_type
            if mission.billing_mode == "TIME_SPENT" and  self.cleaned_data["detail_type"] != "TIME_SPENT_MISSION":
                raise invalid_type
        return self.cleaned_data