# coding: utf-8
"""
Database access layer for pydici billing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from datetime import date, timedelta
from time import strftime
from os.path import join

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext

from pydici.leads.models import Lead
from pydici.expense.models import Expense
import pydici.settings


# This utils function is here and not in utils module
# to avoid circular import loop, as utils module import models
def bill_file_path(instance, filename):
    """Format full path of bill path"""
    return join(pydici.settings.PYDICI_ROOTDIR, "data", "bill",
                strftime("%Y"), strftime("%m"),
                u"%s_%s_%s" % (strftime("%d-%H%M%S"), instance.bill_id, filename))


class Bill(models.Model):
    BILL_STATE = (
            ('1_SENT', ugettext("Sent")),
            ('2_PAID', ugettext("Paid")),
            ('3_LITIGIOUS', ugettext("Litigious")),
            ('4_CANCELED', ugettext("Canceled")),)
    BILL_NATURE = (
            ('1_CLIENT', ugettext("Client")),
            ('2_SUPPLIER', ugettext("Supplier")),)

    lead = models.ForeignKey(Lead, verbose_name=_("Lead"))
    bill_id = models.CharField(_("Bill id"), max_length=500)
    amount = models.DecimalField(_(u"Amount (€ excl tax)"), max_digits=10, decimal_places=2)
    amount_with_vat = models.DecimalField(_(u"Amount (€ incl tax)"), max_digits=10, decimal_places=2, blank=True, null=True)
    vat = models.DecimalField(_(u"VAT (%)"), max_digits=4, decimal_places=2, default=pydici.settings.PYDICI_DEFAULT_VAT_RATE)
    creation_date = models.DateField(_("Creation date"), default=date.today())
    due_date = models.DateField(_("Due date"), default=(date.today() + timedelta(30)))
    payment_date = models.DateField(_("Payment date"), blank=True, null=True)
    state = models.CharField(_("State"), max_length=30, choices=BILL_STATE, default="1_SENT")
    previous_year_bill = models.BooleanField(_("Previous year bill"), default=False)
    comment = models.CharField(_("Comments"), max_length=500, blank=True, null=True)
    nature = models.CharField(_("Nature"), max_length=30, choices=BILL_NATURE, default="1_CLIENT")
    expenses = models.ManyToManyField(Expense, blank=True, limit_choices_to={"chargeable":True})
    expenses_with_vat = models.BooleanField(_("Charge expense with VAT"), default=True)
    bill_file = models.FileField(_("File"), upload_to=bill_file_path)

    def __unicode__(self):
        if self.bill_id:
            return u"%s (%s)" % (self.bill_id, self.id)
        else:
            return unicode(self.id)

    def client(self):
        if self.lead.paying_authority:
            return u"%s via %s" % (self.lead, self.lead.paying_authority.short_name())
        else:
            return unicode(self.lead)

    def save(self, force_insert=False, force_update=False):
        # Save it first to define pk and allow browsing relationship
        super(Bill, self).save(force_insert, force_update)
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
                    #TODO: handle expense without VAT
                    self.amount_with_vat += expense.amount
        super(Bill, self).save(force_insert, force_update) # Save again

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

    class Meta:
        ordering = ["lead__client__organisation__company", "creation_date"]
        verbose_name = _("Bill")
