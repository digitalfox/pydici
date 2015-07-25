# coding: utf-8
"""
Database access layer for pydici billing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from datetime import date, timedelta
from time import strftime
from os.path import join, dirname
import os.path
from decimal import Decimal

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.core.files.storage import FileSystemStorage
from django.core.urlresolvers import reverse

from leads.models import Lead
from expense.models import Expense
from crm.models import Supplier
from core.utils import sanitizeName
import pydici.settings


# Custom storage that hook static url to custom view
# Really used to have proper link in admin page

class BillStorage(FileSystemStorage):
    def __init__(self, nature="client"):
        super(BillStorage, self).__init__(location=join(pydici.settings.PYDICI_ROOTDIR, "data", "bill", nature))
        self.nature = nature

    def url(self, name):
        try:
            bill_id = os.path.split(dirname(name))[1]
            if self.nature == "client":
                bill = ClientBill.objects.get(bill_id=bill_id)
                return reverse("billing.views.bill_file", kwargs={"bill_id": bill.id, "nature": "client"})
            else:
                bill = SupplierBill.objects.get(bill_id=bill_id)
                return reverse("billing.views.bill_file", kwargs={"bill_id": bill.id, "nature": "supplier"})
        except Exception:
            # Don't display URL if Bill does not exist or path is invalid
            return ""


# This utils function is here and not in utils module
# to avoid circular import loop, as utils module import models
def bill_file_path(instance, filename):
    """Format relative path to Storage of bill"""
    return join(strftime("%Y"), strftime("%m"),
                instance.bill_id, sanitizeName(filename))


def default_due_date():
    return date.today() + timedelta(30)


class AbstractBill(models.Model):
    """Abstract class that factorize ClientBill and SupplierBill fields and logic"""
    lead = models.ForeignKey(Lead, verbose_name=_("Lead"))
    bill_id = models.CharField(_("Bill id"), max_length=200, unique=True)
    creation_date = models.DateField(_("Creation date"), auto_now_add=True)
    due_date = models.DateField(_("Due date"), default=default_due_date)
    payment_date = models.DateField(_("Payment date"), blank=True, null=True)
    previous_year_bill = models.BooleanField(_("Previous year bill"), default=False)
    comment = models.CharField(_("Comments"), max_length=500, blank=True, null=True)
    amount = models.DecimalField(_(u"Amount (€ excl tax)"), max_digits=10, decimal_places=2)
    amount_with_vat = models.DecimalField(_(u"Amount (€ incl tax)"), max_digits=10, decimal_places=2, blank=True, null=True)
    vat = models.DecimalField(_(u"VAT (%)"), max_digits=4, decimal_places=2, default=Decimal(pydici.settings.PYDICI_DEFAULT_VAT_RATE))
    expenses = models.ManyToManyField(Expense, blank=True, limit_choices_to={"chargeable": True})
    expenses_with_vat = models.BooleanField(_("Charge expense with VAT"), default=True)



    def __unicode__(self):
        if self.bill_id:
            return u"%s (%s)" % (self.bill_id, self.id)
        else:
            return unicode(self.id)

    def payment_wait(self):
        if self.payment_date:
            wait = self.payment_date - self.due_date
        else:
            wait = date.today() - self.due_date
        return wait.days

    def payment_delay(self):
        if self.payment_date:
            wait = self.payment_date - self.creation_date
        else:
            wait = date.today() - self.creation_date
        return wait.days

    def bill_file_url(self):
        """Return url if file exists, else #"""
        try:
            return self.bill_file.url
        except ValueError:
            return "#"

    class Meta:
        abstract = True
        ordering = ["lead__client__organisation__company", "creation_date"]


class ClientBill(AbstractBill):
    CLIENT_BILL_STATE = (
            ('1_SENT', ugettext("Sent")),
            ('2_PAID', ugettext("Paid")),
            ('3_LITIGIOUS', ugettext("Litigious")),
            ('4_CANCELED', ugettext("Canceled")),)
    state = models.CharField(_("State"), max_length=30, choices=CLIENT_BILL_STATE, default="1_SENT")
    bill_file = models.FileField(_("File"), max_length=500, upload_to=bill_file_path, storage=BillStorage(nature="client"))

    def client(self):
        if self.lead.paying_authority:
            return u"%s via %s" % (self.lead, self.lead.paying_authority.short_name())
        else:
            return unicode(self.lead)

    def save(self, *args, **kwargs):
        # Save it first to define pk and allow browsing relationship
        super(ClientBill, self).save(*args, **kwargs)
        # Automatically set payment date for paid bills
        if self.state == "2_PAID" and not self.payment_date:
            self.payment_date = date.today()
        # Automatically switch as paid bills with payment date
        elif self.state == "1_SENT" and self.payment_date:
            self.state = "2_PAID"
        # Automatically compute amount with VAT if not defined
        if not self.amount_with_vat:
            self.amount_with_vat = self.amount * (1 + self.vat / 100)
            if self.expenses.count():
                for expense in self.expenses.all():
                    # TODO: handle expense without VAT
                    self.amount_with_vat += expense.amount
        super(ClientBill, self).save(*args, **kwargs)  # Save again

    class Meta:
        verbose_name = _("Client Bill")


class SupplierBill(AbstractBill):
    SUPPLIER_BILL_STATE = (
            ('1_RECEIVED', ugettext("Received")),
            ('2_PAID', ugettext("Paid")),
            ('3_LITIGIOUS', ugettext("Litigious")),
            ('4_CANCELED', ugettext("Canceled")),)
    state = models.CharField(_("State"), max_length=30, choices=SUPPLIER_BILL_STATE, default="1_RECEIVED")
    bill_file = models.FileField(_("File"), max_length=500, upload_to=bill_file_path, storage=BillStorage(nature="supplier"))
    supplier = models.ForeignKey(Supplier)
    supplier_bill_id = models.CharField(_("Supplier Bill id"), max_length=200)

    def save(self, *args, **kwargs):
        # Save it first to define pk and allow browsing relationship
        super(SupplierBill, self).save(*args, **kwargs)
        # Automatically set payment date for paid bills
        if self.state == "2_PAID" and not self.payment_date:
            self.payment_date = date.today()
        # Automatically switch as paid bills with payment date
        elif self.state == "1_RECEIVED" and self.payment_date:
            self.state = "2_PAID"
        super(SupplierBill, self).save(*args, **kwargs)


    class Meta:
        verbose_name = _("Supplier Bill")
        unique_together = (("supplier", "supplier_bill_id"),)
