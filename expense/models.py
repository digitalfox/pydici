# coding: utf-8
"""
Database access layer for pydici expense module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from time import strftime
from os.path import join, dirname, split
import mimetypes
from io import BytesIO
from base64 import b64encode

from django.db import models
from django.core.files.storage import FileSystemStorage
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.contrib.auth.models import User
from django.conf import settings

from leads.models import Lead
from core.utils import sanitizeName


EXPENSE_STATES = (
    ("REQUESTED", _("Requested")),
    ("VALIDATED", _("Validated")),
    ("REJECTED", _("Rejected")),
    ("NEEDS_INFORMATION", _("Needs information")),
    ("CONTROLLED", _("Controlled")),
    ("PAID", _("Paid")),
)

EXPENSE_TRANSITION_TO_STATES = (
    ("VALIDATED", ugettext("Validate")),
    ("REJECTED", ugettext("Reject")),
    ("NEEDS_INFORMATION", ugettext("Ask for information")),
    ("CONTROLLED", ugettext("Control")),
)

class ExpenseStorage(FileSystemStorage):
    def url(self, name):
        try:
            expense_id = split(dirname(name))[1]
            return reverse("expense:expense_receipt", kwargs={"expense_id": expense_id})
        except Exception:
            # Don't display URL if Expense does not exist or path is invalid
            return ""


# This utils function is here and not in utils module
# to avoid circular import loop, as utils module import Expense models
def expense_receipt_path(instance, filename):
    """Format full path of expense receipt"""
    return join(settings.PYDICI_ROOTDIR, "data", "expense",
                strftime("%Y"), strftime("%m"), instance.user.username,
                "%s_%s" % (strftime("%d-%H%M%S"), sanitizeName(filename)))


class ExpenseCategory(models.Model):
    """Category of an expense."""
    name = models.CharField(_("Name"), max_length=50)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Expense category")
        verbose_name_plural = _("Expense categories")


class ExpensePayment(models.Model):
    """Payment (reimbursement) of a set of expenses to a consultant"""
    payment_date = models.DateField(_("Payment date"))

    def user(self):
        if self.expense_set.exists():
            return self.expense_set.all()[0].user

    def amount(self):
        amount = 0
        for expense in self.expense_set.all():
            amount += expense.amount
        return amount

    def get_absolute_url(self):
        return reverse('expense:expense_payment_detail', args=[str(self.id)])


    class Meta:
        verbose_name = _("Expenses payment")
        verbose_name_plural = _("Expenses payments")


class Expense(models.Model):
    """Consultant expense"""
    description = models.CharField(_("Description"), max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    lead = models.ForeignKey(Lead, null=True, blank=True, verbose_name=_("Lead"), on_delete=models.CASCADE)
    chargeable = models.BooleanField(_("Chargeable"))
    creation_date = models.DateField(_("Date"), auto_now_add=True)
    expense_date = models.DateField(_("Expense date"))
    update_date = models.DateTimeField(_("Updated"), auto_now=True)
    amount = models.DecimalField(_("Amount"), max_digits=7, decimal_places=2)
    category = models.ForeignKey(ExpenseCategory, verbose_name=_("Category"), on_delete=models.CASCADE)
    receipt = models.FileField(_("Receipt"), max_length=500, upload_to=expense_receipt_path, storage=ExpenseStorage(), null=True, blank=True)
    corporate_card = models.BooleanField(_("Paid with corporate card"), default=False)
    comment = models.TextField(_("Comments"), blank=True)
    workflow_in_progress = models.BooleanField(default=True)
    expensePayment = models.ForeignKey(ExpensePayment, blank=True, null=True, on_delete=models.SET_NULL)
    state = models.CharField(_("state"), choices=EXPENSE_STATES, default="REQUESTED", max_length=20)

    def __str__(self):
        if self.lead:
            return "%s (%s %s %s) - %s € - %s" % (self.description, self.lead, self.lead.deal_id, self.expense_date, self.amount, self.get_state_display())
        else:
            return "%s (%s) - %s € - %s" % (self.description, self.expense_date, self.amount, self.get_state_display())


    def receipt_data(self):
        """Return receipt data in formated way to be included inline in a html page"""
        response = ""
        if self.receipt:
            content_type = self.receipt_content_type()
            data = BytesIO()
            for chunk in self.receipt.chunks():
                data.write(chunk)

            data = b64encode(data.getvalue()).decode()
            if content_type == "application/pdf":
                response = "<object data='data:application/pdf;base64,%s' type='application/pdf' width='100%%' height='100%%'></object>" % data
            else:
                response = "<img src='data:%s;base64,%s'>" % (content_type, data)

        return response

    def receipt_content_type(self):
        if self.receipt:
            return mimetypes.guess_type(self.receipt.name)[0] or "application/stream"


    def get_absolute_url(self):
        return reverse('expense:expenses', args=[str(self.id)])

    class Meta:
        verbose_name = _("Expense")
        verbose_name_plural = _("Expenses")
        ordering = ["-expense_date", ]
