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
from django.utils.translation import ugettext_lazy
from django.core.exceptions import ValidationError

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div, Column, Field
import workflows.utils as wf
from django_select2.forms import ModelSelect2MultipleWidget, ModelSelect2Widget

from expense.models import Expense
from leads.forms import CurrentLeadChoices
from core.forms import PydiciCrispyForm


class ExpenseChoices(ModelSelect2Widget):
    #TODO: factorize this
    model = Expense
    search_fields = ["description__icontains", "user__first_name__icontains", "user__last_name__icontains",
                     "lead__name__icontains", "lead__deal_id__icontains", "lead__client__organisation__name",
                     "lead__client__organisation__company__name__icontains",
                     "lead__client__organisation__company__code__icontains"]

class ExpenseMChoices(ModelSelect2MultipleWidget):
    model = Expense
    search_fields = ["description__icontains", "user__first_name__icontains", "user__last_name__icontains",
                     "lead__name__icontains", "lead__deal_id__icontains", "lead__client__organisation__name",
                     "lead__client__organisation__company__name__icontains", "lead__client__organisation__company__code__icontains"]


class ChargeableExpenseMChoices(ExpenseMChoices):
    model = Expense

    def get_queryset(self):
        return Expense.objects.filter(chargeable=True)


class PayableExpenseMChoices(ExpenseMChoices):
    """Expenses that are payable to consultants"""
    def get_queryset(self):
        expenses = Expense.objects.filter(workflow_in_progress=True, corporate_card=False, expensePayment=None)
        # Filter on expenses that really terminate their workflow.
        expenses_id = [expense.id for expense in expenses if wf.get_state(expense).transitions.count() == 0]
        # Recreate a queryset that match thoses expenses
        expenses = Expense.objects.filter(id__in=expenses_id)
        return expenses


class ExpenseForm(forms.ModelForm):
    """Expense form based on Expense model"""
    class Meta:
        model = Expense
        fields = ("description", "lead", "chargeable", "amount", "category", "receipt", "expense_date", "corporate_card", "comment")
        widgets = {"description": TextInput(attrs={"size": 40}),  # Increase default size
                   "comment": Textarea(attrs={'cols': 17, 'rows': 2}),  # Reduce height and increase width
                   "lead": CurrentLeadChoices}


    def __init__(self, *args, **kwargs):
        super(ExpenseForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        submit = Submit("Submit", _("Save"))
        submit.field_classes = "btn btn-default"
        self.helper.layout = Layout(Div(Column("description", "category", "amount", Field("expense_date", css_class="datepicker"), css_class='col-md-6'),
                                        Column("lead", "chargeable", "corporate_card", "receipt", "comment", css_class='col-md-6'),
                                        css_class='row'),
                                    submit)

    def clean_receipt(self):
        valid_extensions = ["pdf", "png", "jpg", "jpeg"]

        if self.cleaned_data["receipt"]:
            for extension in valid_extensions:
                if self.cleaned_data["receipt"].name.lower().endswith(extension):
                    return self.cleaned_data["receipt"]
            raise ValidationError(ugettext_lazy("Use a valid extension (%s)") % ", ".join(valid_extensions))


    def clean(self):
        """Additional check on expense form"""
        if self.cleaned_data["chargeable"] and not self.cleaned_data["lead"]:
            raise forms.ValidationError(_("You must define a lead if expense is chargeable"))
        return self.cleaned_data


class ExpensePaymentForm(PydiciCrispyForm):
    """Expense payment form based on ExpensePayment model"""
    expenses = forms.ModelMultipleChoiceField(label=_("Expenses"), widget=PayableExpenseMChoices(attrs={'data-placeholder':_("Select expenses to pay...")}), queryset=Expense.objects)
    payment_date = forms.fields.DateField(label=_("payment date"), widget=forms.widgets.DateInput(format="%d/%m/%Y"), input_formats=["%d/%m/%Y",])

    def __init__(self, *args, **kwargs):
        super(ExpensePaymentForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column("expenses", css_class="col-md-3"),
                                        Column(Field("payment_date", css_class="datepicker"), css_class="col-md-3"),
                                        css_class="row"),
                                    self.submit)


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