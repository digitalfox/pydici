# coding:utf-8
"""
Expense form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django import forms
from django.forms.widgets import TextInput, Textarea
from django.utils.translation import ugettext as _
from django.core.exceptions import ValidationError


from ajax_select.fields import AutoCompleteSelectField, AutoCompleteSelectMultipleField

from expense.models import Expense, ExpensePayment


class ExpenseForm(forms.ModelForm):
    """Expense form based on Expense model"""
    class Meta:
        model = Expense
        fields = ("description", "lead", "chargeable", "amount", "category", "receipt", "expense_date", "corporate_card", "comment")
        widgets = {"description": TextInput(attrs={"size": 40}),  # Increase default size
                   "comment": Textarea(attrs={'cols': 17, 'rows': 2})}  # Reduce height and increase width

    lead = AutoCompleteSelectField('lead', required=False, label=_("Lead"))  # Ajax it

    def clean(self):
        """Additional check on expense form"""
        if self.cleaned_data["chargeable"] and not self.cleaned_data["lead"]:
            raise forms.ValidationError(_("You must define a lead if expense is chargeable"))
        return self.cleaned_data


class ExpensePaymentForm(forms.Form):
    """Expense payment form based on ExpensePayemnt model"""
    expenses = AutoCompleteSelectMultipleField('payable_expense', required=True, label=_("Expenses"))  # Ajax it
    payment_date = forms.fields.DateField()

    def clean(self):
        """Ensure expenses belongs to the same users"""
        if "expenses" in self.cleaned_data:
            user = None
            for expense_id in self.cleaned_data["expenses"]:
                expense = Expense.objects.get(id=expense_id)
                if user is None:
                    user = expense.user
                else:
                    if expense.user != user:
                        raise ValidationError(_("All expenses of a payment must belongs to same user"))
        return self.cleaned_data

    class Meta:
        model = ExpensePayment
        fields = ("payment_date", "expenses")
