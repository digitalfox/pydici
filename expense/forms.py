# coding:utf-8
"""
Expense form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
import copy

from django import forms
from django.forms.widgets import TextInput, Textarea
from django.utils.translation import ugettext as _
from django.core.exceptions import ValidationError

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div, Column, Field
from django_select2.fields import AutoModelSelect2MultipleField
from django_select2.views import NO_ERR_RESP
import workflows.utils as wf

from expense.models import Expense, ExpensePayment
from leads.forms import LeadChoices
from core.forms import PydiciSelect2Field


class ExpenseMChoices(PydiciSelect2Field, AutoModelSelect2MultipleField):
    queryset = Expense.objects
    search_fields = ["description__icontains", "user__first_name__icontains", "user__last_name__icontains",
                     "lead__name__icontains", "lead__deal_id__icontains", "lead__client__organisation__name",
                     "lead__client__organisation__company__name__icontains", "lead__client__organisation__company__code__icontains"]


class ChargeableExpenseMChoices(ExpenseMChoices):
    queryset = Expense.objects.filter(chargeable=True)


class PayableExpenseMChoices(ExpenseMChoices):
    queryset = Expense.objects.filter(workflow_in_progress=True, corporate_card=False, expensePayment=None)

    def get_results(self, request, term, page, context):
        """ Override standad method to filter according to wrokflow state. Cannot be done in a simple query set..."""
        qs = copy.deepcopy(self.get_queryset())
        params = self.prepare_qs_params(request, term, self.search_fields)

        if self.max_results:
            min_ = (page - 1) * self.max_results
            max_ = min_ + self.max_results + 1  # fetching one extra row to check if it has more rows.
            res = list(qs.filter(*params['or'], **params['and'])[min_:max_])
            has_more = len(res) == (max_ - min_)
            if has_more:
                res = res[:-1]
        else:
            res = list(qs.filter(*params['or'], **params['and']))
            has_more = False

        res = [expense for expense in res if wf.get_state(expense).transitions.count() == 0]

        res = [(getattr(obj, self.to_field_name), self.label_from_instance(obj), self.extra_data_from_instance(obj))
               for obj in res]
        return (NO_ERR_RESP, has_more, res,)


class ExpenseForm(forms.ModelForm):
    """Expense form based on Expense model"""
    class Meta:
        model = Expense
        fields = ("description", "lead", "chargeable", "amount", "category", "receipt", "expense_date", "corporate_card", "comment")
        widgets = {"description": TextInput(attrs={"size": 40}),  # Increase default size
                   "comment": Textarea(attrs={'cols': 17, 'rows': 2})}  # Reduce height and increase width

    lead = LeadChoices(required=False, label=_("Lead"))

    def __init__(self, *args, **kwargs):
        super(ExpenseForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        submit = Submit("Submit", _("Save"))
        submit.field_classes = "btn btn-default"
        self.helper.layout = Layout(Div(Column("description", "category", "amount", Field("expense_date", css_class="datepicker"), css_class='col-md-6'),
                                        Column("lead", "chargeable", "corporate_card", "receipt", "comment", css_class='col-md-6'),
                                        css_class='row'),
                                    submit)

    def clean(self):
        """Additional check on expense form"""
        if self.cleaned_data["chargeable"] and not self.cleaned_data["lead"]:
            raise forms.ValidationError(_("You must define a lead if expense is chargeable"))
        return self.cleaned_data


class ExpensePaymentForm(forms.Form):
    """Expense payment form based on ExpensePayemnt model"""
    expenses = PayableExpenseMChoices(label=_("Expenses"))
    payment_date = forms.fields.DateField(label=_("payment date"))

    def clean(self):
        """Ensure expenses belongs to the same users"""
        if "expenses" in self.cleaned_data:
            user = None
            for expense in self.cleaned_data["expenses"]:
                if user is None:
                    user = expense.user
                else:
                    if expense.user != user:
                        raise ValidationError(_("All expenses of a payment must belongs to same user"))
        return self.cleaned_data

    class Meta:
        model = ExpensePayment
        fields = ("payment_date", "expenses")
