# coding: utf-8
"""
Database access layer for pydici billing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""


from django.db import models
from django.utils.translation import ugettext_lazy as _

from datetime import date

from pydici.leads.models import Lead

class Bill(models.Model):
    BILL_STATE = (
            ('1_SENT', _("Sent")),
            ('2_PAID', _("Paid")),
            ('3_LITIGIOUS', _("Litigious")),
            ('4_CANCELED', _("Canceled")),)

    lead = models.ForeignKey(Lead, verbose_name=_("Lead"))
    bill_id = models.CharField(_("Bill id"), max_length=500, blank=True, null=True)
    amount = models.DecimalField(_(u"Amount (k€ excl tax)"), max_digits=10, decimal_places=3)
    creation_date = models.DateField(_("Creation date"), default=date.today())
    due_date = models.DateField(_("Due date"))
    payment_date = models.DateField(_("Payment date"), blank=True, null=True)
    state = models.CharField(_("State"), max_length=30, choices=BILL_STATE, default="1_SENT")
    previous_year_bill = models.BooleanField(_("Previous year bill"), default=False)
    comment = models.CharField(_("Comments"), max_length=500, blank=True, null=True)

    def __unicode__(self):
        if self.bill_id:
            return u"%s (%s)" % (self.bill_id, self.id)
        else:
            return unicode(self.id)

    def save(self, force_insert=False, force_update=False):
        # Automatically set payment date for paid bills
        if self.state == "2_PAID" and not self.payment_date:
            self.payment_date = date.today()
        # Automatically switch as paid bills with payment date
        elif self.state == "1_SENT" and self.payment_date:
            self.state = "2_PAID"

        super(Bill, self).save(force_insert, force_update)

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
        ordering = ["lead__client__organisation__company"]
        verbose_name = _("Bill")
