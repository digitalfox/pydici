# coding: utf-8
"""
Database access layer for pydici leads module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from django.db import models
from datetime import datetime, date
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.core import urlresolvers

from pydici.core.utils import send_lead_mail, capitalize, compact_text
import pydici.settings

from pydici.core.models import Subsidiary
from pydici.crm.models import Client
from pydici.people.models import Consultant, SalesMan

SHORT_DATETIME_FORMAT = "%d/%m/%y %H:%M"

class LeadManager(models.Manager):
    def active(self):
        return self.get_query_set().exclude(state__in=("LOST", "FORGIVEN", "WON", "SLEEPING"))

    def passive(self):
        return self.get_query_set().filter(state__in=("LOST", "FORGIVEN", "WON", "SLEEPING"))

class Lead(models.Model):
    """A commercial lead"""
    STATES = (
            ('QUALIF', ugettext("Qualifying")),
            ('WRITE_OFFER', ugettext("Writting offer")),
            ('OFFER_SENT', ugettext("Offer sent")),
            ('NEGOTIATION', ugettext("Negotiation")),
            ('WON', ugettext("Won")),
            ('LOST', ugettext("Lost")),
            ('FORGIVEN', ugettext("Forgiven")),
            ('SLEEPING', ugettext("Sleeping")),
           )
    name = models.CharField(_("Name"), max_length=200)
    description = models.TextField(blank=True)
    action = models.CharField(_("Action"), max_length=2000, blank=True, null=True)
    sales = models.IntegerField(_(u"Sales (k€)"), blank=True, null=True)
    salesman = models.ForeignKey(SalesMan, blank=True, null=True, verbose_name=_("Salesman"))
    staffing = models.ManyToManyField(Consultant, blank=True)
    external_staffing = models.CharField(_("External staffing"), max_length=300, blank=True)
    responsible = models.ForeignKey(Consultant, related_name="%(class)s_responsible", verbose_name="Responsable", blank=True, null=True)
    start_date = models.DateField(_("Starting"), blank=True, null=True)
    due_date = models.DateField(_("Due"), blank=True, null=True)
    state = models.CharField(_("State"), max_length=30, choices=STATES)
    client = models.ForeignKey(Client)
    creation_date = models.DateTimeField(_("Creation"), default=datetime.now())
    update_date = models.DateTimeField(_("Updated"), auto_now=True)
    send_email = models.BooleanField(_("Send lead by email"), default=True)

    objects = LeadManager() # Custom manager that factorise active/passive lead code

    def __unicode__(self):
        return u"%s - %s" % (self.client.organisation, self.name)

    def save(self, force_insert=False, force_update=False):
        self.description = compact_text(self.description)
        super(Lead, self).save(force_insert, force_update)

    def staffing_list(self):
        staffing = ""
        if self.staffing:
            staffing += ", ".join(x["trigramme"] for x in self.staffing.values())
        if self.external_staffing:
            staffing += ", (%s)" % self.external_staffing
        return staffing

    def update_date_strf(self):
        return self.update_date.strftime(SHORT_DATETIME_FORMAT)
    update_date_strf.short_description = _("Updated")

    def short_description(self):
        max_length = 20
        if len(self.description) > max_length:
            return self.description[:max_length] + "..."
        else:
            return self.description
    short_description.short_description = _("Description")

    def is_late(self):
        """@return: True if due date is today or in the past.
        False if not defined or in the future"""
        if self.due_date and self.due_date <= date.today():
            return True
        else:
            return False

    class Meta:
        ordering = ["client__organisation__company__name", "name"]
        verbose_name = _("Lead")
