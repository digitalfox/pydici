# coding: utf-8
"""
Database access layer for pydici expense module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from time import strftime
from os.path import join

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.contrib.auth.models import User
import workflows.utils as wf

from pydici.leads.models import Lead
import pydici.settings

# This utils function is here and not in utils module
# to avoid circular import loop, as utils module import Expense models
def expense_receipt_path(instance, filename):
    """Format full path of expense receipt"""
    return join(pydici.settings.PYDICI_ROOTDIR, "data", "expense",
                strftime("%Y"), strftime("%m"), instance.user.username,
                strftime("%d-%H%M%S_" + filename))


class ExpenseCategory(models.Model):
    """Category of an expense."""
    name = models.CharField(_("Name"), max_length=50)

    def __unicode__(self):
        return self.name


class Expense(models.Model):
    """Consultant expense"""
    description = models.CharField(_("Description"), max_length=200)
    user = models.ForeignKey(User)
    lead = models.ForeignKey(Lead, null=True, blank=True)
    chargeable = models.BooleanField(_("Chargeable"))
    creation_date = models.DateField(_("Date"))
    expense_date = models.DateField(_("Expense date"))
    update_date = models.DateTimeField(_("Updated"), auto_now=True)
    amount = models.DecimalField(_("Amount"), max_digits=7, decimal_places=2)
    category = models.ForeignKey(ExpenseCategory, verbose_name=_("Category"))
    receipt = models.FileField(_("Receipt"), upload_to=expense_receipt_path, null=True, blank=True)
    corporate_card = models.BooleanField(_("Paid with corporate card"), default=False)
    comment = models.TextField(_("Comments"), blank=True)
    workflow_in_progress = models.BooleanField(default=True)

    def __unicode__(self):
        if self.lead:
            return u"%s (%s) - %s €" % (self.description, self.lead, self.amount)
        else:
            return u"%s - %s €" % (self.description, self.amount)

    def state(self):
        """expense state according to expense workflow"""
        return wf.get_state(self).name

    def transitions(self, user):
        """expense allowed transitions in workflows for given user"""
        if self.workflow_in_progress:
            return wf.get_allowed_transitions(self, user)
        else:
            return []
