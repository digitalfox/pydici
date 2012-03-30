# coding: utf-8
"""
Database access layer for pydici CRM module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta

from django.db import models
from django.db.models import Sum, Q
from django.utils.translation import ugettext_lazy as _

from pydici.core.utils import capitalize

SHORT_DATETIME_FORMAT = "%d/%m/%y %H:%M"


class AbstractCompany(models.Model):
    """Abstract Company base class for subsidiary, client/supplier/broker/.. company"""
    name = models.CharField(_("Name"), max_length=200, unique=True)
    code = models.CharField(_("Code"), max_length=3, unique=True)

    def __unicode__(self):
        return unicode(self.name)

    class Meta:
        abstract = True


class Subsidiary(AbstractCompany):
    """Internal company / organisation unit"""
    class Meta:
        verbose_name = _("Subsidiary")
        verbose_name_plural = _("Subsidiaries")
        ordering = ["name", ]


class Company(AbstractCompany):
    """Company"""
    def sales(self, onlyLastYear=False):
        """Sales billed for this company in keuros"""
        from pydici.billing.models import ClientBill
        data = ClientBill.objects.filter(lead__client__organisation__company=self)
        if onlyLastYear:
            data = data.filter(creation_date__gt=(date.today() - timedelta(365)))
        if data.count():
            return float(data.aggregate(Sum("amount")).values()[0]) / 1000
        else:
            return 0

    class Meta:
        verbose_name = _("Company")
        verbose_name_plural = _("Companies")
        ordering = ["name", ]


class ClientOrganisation(models.Model):
    """A department in client organization"""
    name = models.CharField(_("Organization"), max_length=200)
    company = models.ForeignKey(Company, verbose_name=_("Client company"))

    def __unicode__(self):
        return u"%s : %s " % (self.company, self.name)

    class Meta:
        ordering = ["company", "name"]
        verbose_name = _("Client organisation")


class Contact(models.Model):
    """Third party contact definition, client contact, broker, business contact etc."""
    name = models.CharField(_("Name"), max_length=200, unique=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(_("Phone"), max_length=30, blank=True)
    mobile_phone = models.CharField(_("Mobile phone"), max_length=30, blank=True)
    fax = models.CharField(_("Fax"), max_length=30, blank=True)
    function = models.CharField(_("Function"), max_length=200, blank=True)

    def __unicode__(self):
        return self.name

    def save(self, *args, **kargs):
        self.name = capitalize(self.name)
        super(Contact, self).save(*args, **kargs)

    def companies(self):
        """Return companies for whom this contact currently works"""
        companies = Company.objects.filter(Q(clientorganisation__client__contact__id=self.id) |
                                           Q(businessbroker__contact__id=self.id) |
                                           Q(supplier__contact__id=self.id)).distinct()
        if companies.count() == 0:
            return _("None")
        elif companies.count() == 1:
            return companies[0]
        elif companies.count() > 1:
            return u", ".join([unicode(i) for i in companies])
    companies.short_description = _("Companies")

    class Meta:
        ordering = ["name"]


class BusinessBroker(models.Model):
    """A business broken: someone that is not a client but an outsider that act
    as a partner to provide some business"""
    company = models.ForeignKey(Company, verbose_name=_("Broker company"))
    contact = models.ForeignKey(Contact, blank=True, null=True, verbose_name=_("Contact"))

    def __unicode__(self):
        if self.company:
            return u"%s (%s)" % (self.company, self.contact)
        else:
            return self.contact

    def short_name(self):
        if self.company:
            return self.company
        else:
            return self.contact

    class Meta:
        ordering = ["company", "contact"]
        verbose_name = _("Business broker")


class Supplier(models.Model):
    """A supplier is defined by a contact and the supplier company where he works at the moment"""
    company = models.ForeignKey(Company, verbose_name=_("Supplier company"))
    contact = models.ForeignKey(Contact, blank=True, null=True, verbose_name=_("Contact"))

    def __unicode__(self):
        if self.contact:
            return u"%s (%s)" % (self.company, self.contact)
        else:
            return unicode(self.company)

    class Meta:
        ordering = ["company", "contact"]
        verbose_name = _("Supplier")


class Client(models.Model):
    """A client is defined by a contact and the organisation where he works at the moment"""
    organisation = models.ForeignKey(ClientOrganisation, verbose_name=_("Organisation"))
    contact = models.ForeignKey(Contact, blank=True, null=True, verbose_name=_("Contact"))
    salesOwner = models.ForeignKey(Subsidiary, verbose_name=_("Sales owner"))

    def __unicode__(self):
        if self.contact:
            return u"%s (%s)" % (self.organisation, self.contact)
        else:
            return unicode(self.organisation)

    def getFinancialConditions(self):
        """Get financial condition for this client by profil
        @return: ((profil1, avgrate1), (profil2, avgrate2)...)"""
        from pydici.staffing.models import FinancialCondition
        data = {}
        for fc in FinancialCondition.objects.filter(mission__lead__client=self,
                                               consultant__timesheet__charge__gt=0, # exclude null charge
                                               consultant__timesheet=models.F("mission__timesheet") # Join to avoid duplicate entries
                                               ).select_related():
            profil = fc.consultant.profil
            if not profil in data:
                data[profil] = []
            data[profil].append(fc.daily_rate)

        # compute average
        data = [(profil, sum(rates) / len(rates)) for profil, rates in data.items()]
        # Sort by profil
        data.sort(key=lambda x: x[0].level)
        return data

    class Meta:
        ordering = ["organisation", "contact"]
        verbose_name = _("Client")


class MissionContact(models.Model):
    """Contact encountered during mission"""
    company = models.ForeignKey(Company, verbose_name=_("company"))
    contact = models.ForeignKey(Contact, verbose_name=_("Contact"))

    def __unicode__(self):
        return u"%s (%s)" % (self.contact, self.company)

    class Meta:
        ordering = ["company", "contact"]
        verbose_name = _("Mission contact")


class AdministrativeFunction(models.Model):
    """Admin functions in a company (sales, HR, billing etc."""
    name = models.CharField(_("Name"), max_length=200, unique=True)

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ("name",)


class AdministrativeContact(models.Model):
    """Administrative contact (team or people) of a company."""
    company = models.ForeignKey(Company, verbose_name=_("company"))
    function = models.ForeignKey(AdministrativeFunction, verbose_name=_("Function"))
    default_phone = models.CharField(_("Phone Switchboard"), max_length=30, blank=True, null=True)
    default_mail = models.EmailField(_("Generic email"), max_length=100, blank=True, null=True)
    default_fax = models.CharField(_("Generic fax"), max_length=100, blank=True, null=True)
    contact = models.ForeignKey(Contact, blank=True, null=True, verbose_name=_("Contact"))

    def phone(self):
        """Best phone number to use"""
        if self.contact:
            # Use contact phone if defined
            if self.contact.mobile_phone:
                return self.contact.mobile_phone
            elif self.contact.phone:
                return self.contact.phone
        # Default to phone switch board
        return self.default_phone

    def email(self):
        """Best email address to use"""
        if self.contact:
            # Use contact email if defined
            if self.contact.email:
                return self.contact.email
        # Default to default team generic email
        return self.default_mail

    def fax(self):
        """Best fax number to use"""
        if self.contact:
            # Use contact fax if defined
            if self.contact.fax:
                return self.contact.fax
        # Default to default team generic fax
        return self.default_fax

    class Meta:
        verbose_name = _("Administrative contact")
        ordering = ("company", "contact")
