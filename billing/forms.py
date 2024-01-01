# coding:utf-8
"""
Bill form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta

from django.forms import ModelForm
from django.utils.translation import gettext_lazy as _
from django.forms.models import BaseInlineFormSet, ModelChoiceField
from django.forms.fields import DateField, TypedChoiceField
from django.forms.widgets import DateInput
from django.forms.utils import ValidationError
from django.utils import formats
from django.utils.safestring import mark_safe
from django.urls import reverse


from crispy_forms.layout import Layout, Div, Column, Row
from crispy_forms.bootstrap import TabHolder, Tab
from crispy_forms.helper import FormHelper
from django_select2.forms import Select2Widget

from billing.models import ClientBill, SupplierBill
from staffing.models import Mission
from expense.models import Expense
from people.models import Consultant
from leads.forms import LeadChoices
from expense.forms import ChargeableExpenseMChoices, ExpenseChoices
from crm.forms import SupplierChoices
from staffing.forms import MissionChoices, LeadMissionChoices
from people.forms import ConsultantChoices
from core.forms import PydiciCrispyModelForm
from core.utils import nextMonth


class BillingDateChoicesField(TypedChoiceField):
    widget = Select2Widget(attrs={'data-placeholder':_("Select a month..."), "data-theme": "bootstrap-5"})

    def __init__(self, *args, **kwargs):
        minDate = kwargs.pop("minDate", date.today() - timedelta(30*11))
        nMonth = kwargs.pop("nMonth", 12)
        months = []
        month = minDate.replace(day=1)
        for i in range(nMonth):
            months.append(month)
            month = nextMonth(month)

        kwargs["choices"] = [(i, formats.date_format(i, format="YEAR_MONTH_FORMAT")) for i in months]
        kwargs["empty_value"] = None

        super(BillingDateChoicesField, self).__init__(*args, **kwargs)

    def has_changed(self, initial, data):
        initial = str(initial) if initial is not None else ''
        return initial != data


class ClientBillForm(PydiciCrispyModelForm):
    class Meta:
        model = ClientBill
        fields = "__all__"
        widgets = { "lead": LeadChoices,
                    "expenses": ChargeableExpenseMChoices}

    def __init__(self, *args, **kwargs):
        super(ClientBillForm, self).__init__(*args, **kwargs)
        self.helper.form_tag = False
        self.helper.layout = Layout(Div(TabHolder(Tab(_("Description"),
                                                      Row(Column("lead"), Column("comment")),
                                                      Row(Column("bill_id"), Column("client_comment")),
                                                      Row(Column("state"), Column("anonymize_profile", "include_timesheet"))),
                                                  Tab(_("Amounts"),
                                                      Column("amount", "vat", "amount_with_vat", css_class="col-md-6")),
                                                  Tab(_("Dates"), Column("creation_date", "due_date", "payment_date",
                                                                         css_class="col-md-6"), ),
                                                  Tab(_("Advanced"), Column("client_deal_id", "lang", "allow_duplicate_expense",
                                                                            "add_facturx_data","bill_file",
                                                                            css_class="col-md-6"), ),
                                                  css_class="row")))

    def clean_amount(self):
        if self.cleaned_data["amount"] or self.data["state"] == "0_DRAFT":
            # Amount is defined or we are in early step, nothing to say
            return self.cleaned_data["amount"]
        else:
            # Amount must be defined
            raise ValidationError(_("Bill amount must be computed from bill detail or defined manually"))

    def clean_add_facturx_data(self):
        if self.cleaned_data["add_facturx_data"]:
            if not self.instance.lead.client.organisation.vat_id or not self.instance.lead.client.organisation.legal_id:
                raise ValidationError(mark_safe(_("You must <a href='%s'>define VAT id and Legal id</a> to generate Facturx data") %
                                        reverse("crm:client_organisation_change",
                                                args=[self.instance.lead.client.organisation.id])))
        return self.cleaned_data["add_facturx_data"]



class SupplierBillForm(PydiciCrispyModelForm):
    class Meta:
        model = SupplierBill
        fields = "__all__"
        widgets = {"lead": LeadChoices,
                   "expenses": ChargeableExpenseMChoices,
                   "supplier": SupplierChoices}

    def __init__(self, *args, **kwargs):
        super(SupplierBillForm, self).__init__(*args, **kwargs)
        self.helper.form_tag = False
        self.helper.layout = Layout(Div(Column("lead", "supplier", "bill_id", "supplier_bill_id", "state", "comment", "bill_file", css_class="col-md-6"),
                                        Column("creation_date", "due_date", "payment_date", "amount", "vat", "amount_with_vat", "expenses", css_class="col-md-6"),
                                        css_class="row"))


class BillDetailInlineFormset(BaseInlineFormSet):
    def add_fields(self, form, index):
        super(BillDetailInlineFormset, self).add_fields(form, index)
        form.fields["mission"] = ModelChoiceField(widget=LeadMissionChoices(lead=self.instance.lead), queryset=Mission.objects)
        form.fields["consultant"] = ModelChoiceField(widget=ConsultantChoices(attrs={"data-allow-clear": False}), queryset=Consultant.objects, required=False)
        form.fields["month"] = BillingDateChoicesField(required=False)

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
        self.field_class = "pydici-bill-input"
        self.template = 'bootstrap5/table_inline_formset.html'


class BillDetailForm(ModelForm):
    def clean(self):
        mission = self.cleaned_data.get("mission", None)
        if mission:
            if mission.billing_mode is None:
                link = reverse("staffing:mission_home", args=[mission.id])
                msg = _("Billing mode of mission <a href='%s'>%s</a> should be defined" % (link, mission.mission_id()))
                raise ValidationError(mark_safe(msg))
            if not self.cleaned_data["month"] and mission.billing_mode=="TIME_SPENT":
                raise ValidationError(_("Month must be defined for time spent mission"))
            if not self.cleaned_data["consultant"] and mission.billing_mode=="TIME_SPENT":
                raise ValidationError(_("Consultant must be defined for time spent mission"))
        return self.cleaned_data


class BillExpenseInlineFormset(BaseInlineFormSet):
    def add_fields(self, form, index):
        super(BillExpenseInlineFormset, self).add_fields(form, index)
        qs = Expense.objects.filter(lead=self.instance.lead, chargeable=True)
        if self.instance.allow_duplicate_expense:
            qs_widget = qs
        else:
            qs_widget = qs.filter(billexpense__isnull=True)  # Don't propose an expense already billed
        form.fields["expense"] = ModelChoiceField(label=_("Expense"), required=False, widget=ExpenseChoices(queryset=qs_widget), queryset=qs)
        form.fields["expense_date"] = DateField(label=_("Expense date"), required=False, widget=DateInput(format="%d/%m/%Y"), input_formats=["%d/%m/%Y",])


    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        expenses = []
        for form in self.forms:
            expense = form.cleaned_data.get("expense", None)
            if expense:
                # ensure expense is unique for this bill
                expense = expense.id
                if expense in expenses:
                    raise ValidationError(_("Cannot declare twice the same expense"))
                expenses.append(expense)
            elif form.cleaned_data.get("amount") or form.cleaned_data.get("amount_with_vat") or form.cleaned_data.get("description"):
                # ensure amount is defined is expense is not provided
                if not (form.cleaned_data.get("amount") or form.cleaned_data.get("amount_with_vat")):
                    raise ValidationError(_("If expense is not selected, please provide at least amount or amount with vat"))



class BillExpenseFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super(BillExpenseFormSetHelper, self).__init__(*args, **kwargs)
        self.form_method = 'post'
        self.form_tag = False
        self.field_class = "pydici-bill-input"
        self.template = 'bootstrap5/table_inline_formset.html'


class BillExpenseForm(ModelForm):
    pass
    #TODO: add sanity checks
