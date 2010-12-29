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

class ThirdPartyContact(models.Model):
    """Third party contact abstract definition"""
    name = models.CharField(_("Name"), max_length=200, unique=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(_("Phone"), max_length=30, blank=True)
    mobile_phone = models.CharField(_("Mobile phone"), max_length=30, blank=True)
    fax = models.CharField(_("Fax"), max_length=30, blank=True)

    def __unicode__(self): return self.name

    def save(self, force_insert=False, force_update=False):
        self.name = capitalize(self.name)
        super(ThirdPartyContact, self).save(force_insert, force_update)

    class Meta:
        abstract = True
        ordering = ["name"]

class ClientContact(ThirdPartyContact):
    """A contact in client organization"""
    function = models.CharField(_("Function"), max_length=200, blank=True)

    def company(self):
        """Return the company for whom this contact works"""
        #return ClientCompany.objects.get(clientorganisation__client__contact__id=self.id)
        companies = ClientOrganisation.objects.filter(client__contact__id=self.id)
        if companies.count() == 0:
            return _("None")
        elif companies.count() == 1:
            return companies[0]
        elif companies.count() > 1:
            return u", ".join([unicode(i) for i in companies])

    company.short_description = _("Company")

    class Meta:
        verbose_name = _("Client contact")

class BusinessBroker(ThirdPartyContact):
    """A business broken: someone that is not a client but an outsider that act
    as a partner to provide some business"""
    company = models.CharField(_("Company"), max_length=200, blank=True)

    def __unicode__(self):
        if self.company:
            return "%s (%s)" % (self.company, self.name)
        else:
            return self.name
    def short_name(self):
        if self.company:
            return self.company
        else:
            return self.name

    class Meta:
        verbose_name = _("Business broker")

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
