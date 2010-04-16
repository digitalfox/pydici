# coding: utf-8
"""
Database access layer for pydici CRM module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext

from pydici.core.utils import capitalize
import pydici.settings

from pydici.core.models import Subsidiary

SHORT_DATETIME_FORMAT = "%d/%m/%y %H:%M"

class ClientCompany(models.Model):
    """Client company"""
    name = models.CharField(_("Name"), max_length=200, unique=True)

    def __unicode__(self): return self.name

    class Meta:
        ordering = ["name"]
        verbose_name = _("Client Company")

class ClientOrganisation(models.Model):
    """A department in client organization"""
    name = models.CharField(_("Organization"), max_length=200)
    company = models.ForeignKey(ClientCompany, verbose_name=_("Client company"))

    def __unicode__(self): return u"%s : %s " % (self.company, self.name)

    class Meta:
        ordering = ["company", "name"]
        verbose_name = _("Client organisation")

class ClientContact(models.Model):
    """A contact in client organization"""
    name = models.CharField(_("Name"), max_length=200, unique=True)
    function = models.CharField(_("Function"), max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(_("Phone"), max_length=30, blank=True)

    def __unicode__(self): return self.name

    def save(self, force_insert=False, force_update=False):
        self.name = capitalize(self.name)
        super(ClientContact, self).save(force_insert, force_update)

    class Meta:
        ordering = ["name"]
        verbose_name = _("Client contact")

class Client(models.Model):
    """A client is defined by a contact and the organisation where he works"""
    organisation = models.ForeignKey(ClientOrganisation, verbose_name=_("Organisation"))
    contact = models.ForeignKey(ClientContact, blank=True, null=True, verbose_name=_("Contact"))
    salesOwner = models.ForeignKey(Subsidiary, verbose_name=_("Sales owner"))

    def __unicode__(self):
        if self.contact:
            return u"%s (%s)" % (self.organisation, self.contact)
        else:
            return u"%s" % (self.organisation)

    class Meta:
        ordering = ["organisation", "contact"]
        verbose_name = _("Client")
