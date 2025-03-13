# coding: utf-8
"""
Database access layer for pydici CRM module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta

from django.db import models
from django.db.models import Sum, Q, F, Avg
from django.apps import apps
from django.utils.translation import gettext_lazy as _
from django.utils.translation import  gettext, pgettext
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.conf import settings

from django_countries.fields import CountryField

from core.utils import GEdge, GEdges, GNode, GNodes
from core.models import CLIENT_BILL_LANG
from crm.utils import get_clients_rate_ranking
from people.tasks import compute_consultant_tasks

SHORT_DATETIME_FORMAT = "%d/%m/%y %H:%M"


class AbstractAddress(models.Model):
    street = models.TextField(_("Street"), blank=True, null=True)
    city = models.CharField(_("City"), max_length=200, blank=True, null=True)
    zipcode = models.CharField(_("Zip code"), max_length=30, blank=True, null=True)
    country = CountryField(_("Country"), null=True, blank=True)
    billing_street = models.TextField(_("Street"), blank=True, null=True)
    billing_city = models.CharField(_("City"), max_length=200, blank=True, null=True)
    billing_zipcode = models.CharField(_("Zip code"), max_length=30, blank=True, null=True)
    billing_country = CountryField(_("Country"), null=True, blank=True)

    def main_address(self):
        return "%s\n%s %s\n%s" % (self.street, self.zipcode, self.city, self.country)

    def billing_address(self):
        return "%s\n%s %s\n%s" % (self.billing_street, self.billing_zipcode, self.billing_city, self.billing_country.name)

    class Meta:
        abstract = True


class AbstractLegalInformation(models.Model):
    legal_description = models.TextField("Legal description", blank=True, null=True)
    legal_id = models.CharField(max_length=30, blank=True, null=True, verbose_name=_("Legal id"))
    vat_id = models.CharField(max_length=30, blank=True, null=True, verbose_name=_("VAT id"))

    class Meta:
        abstract = True

class AbstractCompany(AbstractAddress, AbstractLegalInformation):
    """Abstract Company base class for subsidiary, client/supplier/broker/.. company"""
    name = models.CharField(_("Name"), max_length=200, unique=True)
    code = models.CharField(_("Code"), max_length=3, unique=True)
    web = models.URLField(blank=True, null=True)

    def __str__(self):
        return str(self.name)

    def save(self, *args, **kwargs):
        # If billing address is not defined, use main address
        if not (self.billing_street and self.billing_city and self.billing_zipcode and self.billing_country):
            self.billing_street = self.street
            self.billing_city = self.city
            self.billing_zipcode = self.zipcode
            self.billing_country = self.country
        super(AbstractCompany, self).save(*args, **kwargs)

    class Meta:
        abstract = True


class BusinessSector(models.Model):
    """Business sector of activity"""
    name = models.CharField(_("Name"), max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Business sector")
        verbose_name_plural = _("Business sectors")

class Subsidiary(AbstractCompany):
    """Internal company / organisation unit"""
    payment_description = models.TextField(_("Payment condition description"), blank=True, null=True)
    commercial_name = models.CharField(_("Commercial name"), max_length=200)

    class Meta:
        verbose_name = _("Subsidiary")
        verbose_name_plural = _("Subsidiaries")
        ordering = ["name", ]


class Company(AbstractCompany):
    """Company"""
    businessOwner = models.ForeignKey("people.Consultant", verbose_name=_("Business owner"), related_name="%(class)s_business_owner", null=True, on_delete=models.SET_NULL)
    external_id = models.CharField(max_length=200, blank=True, null=True, unique=True, default=None)
    business_sector = models.ForeignKey("crm.BusinessSector", verbose_name=_("Business sector"), null=True, on_delete=models.SET_NULL)

    def sales(self, onlyLastYear=False, subsidiary=None):
        """Sales billed for this company in keuros"""
        from billing.models import ClientBill
        data = ClientBill.objects.filter(lead__client__organisation__company=self)
        if subsidiary:
            data = data.filter(lead__subsidiary=subsidiary)
        if onlyLastYear:
            data = data.filter(creation_date__gt=(date.today() - timedelta(365)))
        if data.count():
            return float(list(data.aggregate(Sum("amount")).values())[0] or 0) / 1000
        else:
            return 0

    def supplier_billing(self, onlyLastYear=False, subsidiary=None):
        """Supplier billing for this company in keuros"""
        from billing.models import SupplierBill
        data = SupplierBill.objects.filter(lead__client__organisation__company=self)
        if subsidiary:
            data = data.filter(lead__subsidiary=subsidiary)
        if onlyLastYear:
            data = data.filter(creation_date__gt=(date.today() - timedelta(365)))
        if data.count():
            return float(list(data.aggregate(Sum("amount")).values())[0] or 0) / 1000
        else:
            return 0

    def save(self, *args, **kwargs):
        super(Company, self).save(*args, **kwargs)
        # Save client organisation children to trigger attribute heritage if needed
        for clientOrganisation in self.clientorganisation_set.all():
            clientOrganisation.save()


    class Meta:
        verbose_name = _("Company")
        verbose_name_plural = _("Companies")
        ordering = ["name", ]


class ClientOrganisation(AbstractAddress, AbstractLegalInformation):
    """A department in client organization"""
    name = models.CharField(_("Organization"), max_length=200)
    company = models.ForeignKey(Company, verbose_name=_("Client company"), on_delete=models.CASCADE)
    business_sector = models.ForeignKey("crm.BusinessSector", verbose_name=_("Business sector"), null=True, blank=True, on_delete=models.SET_NULL)
    billing_name = models.CharField(max_length=200, null=True, blank=True, verbose_name=_("Name used for billing"))
    billing_contact = models.ForeignKey("AdministrativeContact", null=True, blank=True,
                                        verbose_name=_("Billing contact"), on_delete=models.SET_NULL)
    billing_lang = models.CharField(_("Billing language"), max_length=10, choices=CLIENT_BILL_LANG,
                                    default=settings.LANGUAGE_CODE)

    def __str__(self):
        return "%s : %s " % (self.company, self.name)

    def save(self, *args, **kwargs):
        heritage_from_company = ("legal_id", "vat_id", "street", "city", "zipcode", "country",
                                 "billing_street", "billing_city", "billing_zipcode", "billing_country", "business_sector")
        for attr in heritage_from_company:
            if not getattr(self, attr):
                setattr(self, attr, getattr(self.company, attr))

        if self.company.businessOwner:
            compute_consultant_tasks.delay(self.company.businessOwner.id)

        super(ClientOrganisation, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("crm:client_organisation", args=[self.id, ])

    class Meta:
        ordering = ["company", "name"]
        verbose_name = _("Client organisation")
        unique_together = ("name", "company")


class Contact(models.Model):
    """Third party contact definition, client contact, broker, business contact etc."""
    name = models.CharField(_("Name"), max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(_("Phone"), max_length=30, blank=True)
    mobile_phone = models.CharField(_("Mobile phone"), max_length=30, blank=True)
    fax = models.CharField(_("Fax"), max_length=30, blank=True)
    function = models.CharField(_("Function"), max_length=200, blank=True)
    contact_points = models.ManyToManyField("people.Consultant", verbose_name="Points of contact", blank=True)
    external_id = models.CharField(max_length=200, blank=True, null=True, unique=True, default=None)

    def __str__(self):
        return self.name

    def companies(self, html=False):
        """Return companies for whom this contact currently works"""
        companies = list(Company.objects.filter(Q(clientorganisation__client__contact__id=self.id) |
                                           Q(businessbroker__contact__id=self.id) |
                                           Q(missioncontact__contact__id=self.id) |
                                           Q(administrativecontact__contact__id=self.id) |
                                           Q(supplier__contact__id=self.id)).distinct())
        companies_count = len(companies)
        if companies_count == 0:
            return _("None")
        elif companies_count == 1:
            if html:
                return mark_safe("<a href='%s'>%s</a>" % (reverse("crm:company_detail", args=[companies[0].id,]), escape(companies[0])))
            else:
                return companies[0]
        elif companies_count > 1:
            if html:
                return mark_safe(", ".join(["<a href='%s'>%s</a>" % (reverse("crm:company_detail", args=[i.id,]), escape(i)) for i in companies]))
            else:
                return ", ".join([str(i) for i in companies])
    companies.short_description = _("Companies")

    def companies_html(self):
        return self.companies(html=True)

    def relationData(self):
        """Compute relational data in json format usable by Dagre / D3 library"""
        nodes = GNodes()
        edges = GEdges()
        leadColor = "#8AA7FF"
        directColor= "#82D887"
        missionColor = "#E4C160"

        try:
            me = GNode(str(self.id), str(self), color="#EEE")
            nodes.add(me)
            # Mission relations
            for missionContact in self.missioncontact_set.all():
                for mission in missionContact.mission_set.all():
                    missionNode = GNode("mission-%s" % mission.id, """<i class="bi bi-gear"></i> 
                                                                      <span class='graph-tooltip' title='%s'><a href='%s'>%s&nbsp;</a></span>""" % (mission.short_name(),
                                                                                                                                                          mission.get_absolute_url(),
                                                                                                                                                          mission.mission_id()))
                    nodes.add(missionNode)
                    edges.append(GEdge(me, missionNode, color=missionColor))
                    for consultant in mission.consultants():
                        consultantNode = GNode("consultant-%s" % consultant.id, str(consultant))
                        nodes.add(consultantNode)
                        edges.append(GEdge(missionNode, consultantNode, color=missionColor))
            # Business / Lead relations
            for client in self.client_set.all():
                if client.lead_set.count() < 5 :
                    for lead in client.lead_set.all():
                        leadNode = GNode("lead-%s" % lead.id, """<i class="bi bi-calculator"></i>
                                                                 <span class='graph-tooltip' title='%s'><a href='%s'>%s&nbsp;</a></span>""" % (str(lead),
                                                                                                                                               lead.get_absolute_url(),
                                                                                                                                               lead.deal_id))
                        nodes.add(leadNode)
                        edges.append(GEdge(me,leadNode, color=leadColor))
                        if lead.responsible:
                            consultantNode = GNode("consultant-%s" % lead.responsible.id, str(lead.responsible))
                            nodes.add(consultantNode)
                            edges.append(GEdge(leadNode, consultantNode, color=leadColor))
                else:
                    # Group link for highly linked contact
                    leads = []
                    responsibles = []
                    for lead in client.lead_set.all():
                        leads.append(lead)
                        if lead.responsible:
                            responsibles.append(lead.responsible)
                    leadsId = "-".join([str(l.id) for l in leads])
                    leadsTitle = str(client.organisation)
                    leadsLabel = _("%s leads" % len(leads))
                    leadsNode = GNode("leads-%s" % leadsId, """<i class="bi bi-calculator"></i>
                                                               <span class='graph-tooltip' title='%s'>&nbsp;%s&nbsp;</span>""" % (leadsTitle, leadsLabel))
                    nodes.add(leadsNode)
                    edges.append(GEdge(me,leadsNode, color=leadColor))
                    for responsible in responsibles:
                        consultantNode = GNode("consultant-%s" % responsible.id, str(responsible))
                        nodes.add(consultantNode)
                        edges.append(GEdge(leadsNode, consultantNode, color=leadColor))

            # Direct contact relation
            for consultant in self.contact_points.all():
                consultantNode = GNode("consultant-%s" % consultant.id, str(consultant))
                nodes.add(consultantNode)
                edges.append(GEdge(me, consultantNode, color=directColor))

            return """var nodes=%s; var edges=%s;""" % (nodes.dump(), edges.dump())

        except Exception as e:
            print(e)

    def get_absolute_url(self):
        return reverse("crm:contact_detail", args=[self.id, ])

    class Meta:
        ordering = ["name"]


class BusinessBroker(models.Model):
    """A business broken: someone that is not a client but an outsider that act
    as a partner to provide some business"""
    company = models.ForeignKey(Company, verbose_name=_("Broker company"), on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, blank=True, null=True, verbose_name=_("Contact"), on_delete=models.SET_NULL)
    billing_name = models.CharField(max_length=200, null=True, blank=True, verbose_name=_("Name used for billing"))

    def __str__(self):
        if self.company:
            if self.contact:
                return "%s (%s)" % (self.company, self.contact)
            else:
                return str(self.company)
        else:
            return self.contact

    def short_name(self):
        if self.company:
            return self.company
        else:
            return self.contact

    def get_absolute_url(self):
        return reverse("crm:businessbroker_update", args=[self.id, ])

    class Meta:
        ordering = ["company", "contact"]
        verbose_name = _("Business broker")
        unique_together = ("company", "contact",)


class Supplier(models.Model):
    """A supplier is defined by a contact and the supplier company where he works at the moment"""
    company = models.ForeignKey(Company, verbose_name=_("Supplier company"), on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, blank=True, null=True, verbose_name=_("Contact"), on_delete=models.SET_NULL)

    def __str__(self):
        if self.contact:
            return "%s (%s)" % (self.company, self.contact)
        else:
            return str(self.company)

    def get_absolute_url(self):
        return reverse("crm:supplier_update", args=[self.id, ])

    class Meta:
        ordering = ["company", "contact"]
        verbose_name = _("Supplier")
        unique_together = ("company", "contact",)


class Client(models.Model):
    """A client is defined by a contact and the organisation where he works at the moment"""
    EXPECTATIONS = (
            ('1_NONE', pgettext("feminine", "None")),
            ('2_DECREASING',  gettext("Decreasing")),
            ('3_FLAT',  gettext("Flat")),
            ('4_INCREASING',  gettext("Increasing")),
           )
    ALIGNMENT = (
            ("1_RESTRAIN",  gettext("To restrain")),
            ("2_STANDARD",  gettext("Standard")),
            ("3_STRATEGIC",  gettext("Strategic")),
                 )
    organisation = models.ForeignKey(ClientOrganisation, verbose_name=_("Company : Organisation"), on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, blank=True, null=True, verbose_name=_("Contact"), on_delete=models.SET_NULL)
    expectations = models.CharField(max_length=30, choices=EXPECTATIONS, default=EXPECTATIONS[2][0], verbose_name=_("Expectations"))
    alignment = models.CharField(max_length=30, choices=ALIGNMENT, default=ALIGNMENT[1][0], verbose_name=_("Strategic alignment"))
    active = models.BooleanField(_("Active"), default=True)

    def __str__(self):
        if self.contact:
            return "%s (%s)" % (self.organisation, self.contact)
        else:
            return str(self.organisation)

    def getFinancialConditions(self, subsidiary=None):
        """Get financial condition for this client by profil
        @return: ((profil1, avgrate1), (profil2, avgrate2)...)"""
        FinancialCondition = apps.get_model("staffing", "FinancialCondition")
        ConsultantProfile = apps.get_model("people", "ConsultantProfile")
        data = []

        financialConditions = FinancialCondition.objects.filter(mission__lead__client=self,
                                          consultant__timesheet__charge__gt=0,  # exclude null charge
                                          consultant__timesheet=F("mission__timesheet") # Join to avoid duplicate entries
                                          )
        if subsidiary:
            financialConditions = financialConditions.filter(mission__lead__subsidiary=subsidiary)

        financialConditions = financialConditions.values("consultant__profil").annotate(Avg("daily_rate")).order_by("consultant__profil__level")
        financialConditions =  financialConditions.values("consultant__profil__name", "daily_rate__avg")
        financialConditions = {p["consultant__profil__name"]: p["daily_rate__avg"] for p in financialConditions}

        for profil in ConsultantProfile.objects.all():
            data.append([profil.name, financialConditions.get(profil.name)])

        return data

    def daily_rate_ranking(self, subsidiary=None):
        """compute daily rate ranking and return (ranking, average daily rate)"""
        financialConditions = get_clients_rate_ranking(subsidiary)
        daily_rate = dict(financialConditions).get(self.id)
        if daily_rate:
            rank = [c[0] for c in financialConditions].index(self.id) + 1
        else:
            rank = None

        return rank, daily_rate

    def objectiveMargin(self, subsidiary=None):
        """Compute margin over budget objective across all mission of this client
        @return: list of (margin in €, margin in % of total turnover) for internal consultant and subcontractor"""
        Mission = apps.get_model("staffing", "Mission")  # Get Mission with get_model to avoid circular imports
        consultantMargin = 0
        subcontractorMargin = 0

        for mission in Mission.objects.filter(lead__client=self):
            for consultant, margin in list(mission.objectiveMargin().items()):
                if subsidiary and consultant.company != subsidiary:
                    continue
                if consultant.subcontractor:
                    subcontractorMargin += margin
                else:
                    consultantMargin += margin
        sales = self.sales()
        if sales > 0:
            consultantMargin_pc = 100 * consultantMargin / (1000 * sales)
            subcontractorMargin_pc = 100 * subcontractorMargin / (1000 * sales)
        else:
            consultantMargin_pc = 0
            subcontractorMargin_pc = 0
        return (consultantMargin, consultantMargin_pc), (subcontractorMargin, subcontractorMargin_pc)

    def fixedPriceMissionMargin(self, subsidiary=None):
        """Compute total fixed price margin in €  mission for this client. Only finished mission (ie archived) are
        considered"""
        Mission = apps.get_model("staffing", "Mission")  # Get Mission with get_model to avoid circular imports
        margin = 0
        missions = Mission.objects.filter(lead__client=self, active=False,
                                          lead__state = "WON", billing_mode="FIXED_PRICE")
        if subsidiary:
            missions = missions.filter(subsidiary=subsidiary)
        for mission in missions:
            margin += mission.remaining()
        return margin * 1000

    def sales(self, onlyLastYear=False, subsidiary=None):
        """Sales billed for this client in keuros"""
        from billing.models import ClientBill
        data = ClientBill.objects.filter(lead__client=self)
        if subsidiary:
            data = data.filter(lead__subsidiary=subsidiary)
        if onlyLastYear:
            data = data.filter(creation_date__gt=(date.today() - timedelta(365)))
        if data.count():
            return float(list(data.aggregate(Sum("amount")).values())[0] or 0) / 1000
        else:
            return 0

    def getActiveLeads(self):
        """@return: list (qs) of active leads for this client"""
        return self.lead_set.exclude(state__in=("LOST", "FORGIVEN", "SLEEPING"))

    def getActiveMissions(self):
        """@return: list of active missions for this client"""
        missions = list()
        for lead in self.getActiveLeads():
            missions.extend(lead.mission_set.filter(active=True))
        return missions

    def main_address(self):
        return self.organisation.main_address()

    def billing_address(self):
        return self.organisation.billing_address()

    def get_absolute_url(self):
        return reverse("crm:company_detail", args=[self.organisation.company.id, ])

    class Meta:
        ordering = ["organisation", "contact"]
        verbose_name = _("Client")
        unique_together = ("organisation", "contact",)


class MissionContact(models.Model):
    """Contact encountered during mission"""
    company = models.ForeignKey(Company, verbose_name=_("company"), on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, verbose_name=_("Contact"), on_delete=models.CASCADE)

    def __str__(self):
        return "%s (%s)" % (self.contact, self.company)

    def get_absolute_url(self):
        return reverse("crm:contact_detail", args=[self.contact.id, ])

    class Meta:
        ordering = ["company", "contact"]
        verbose_name = _("Mission contact")
        unique_together = ("company", "contact",)


class AdministrativeFunction(models.Model):
    """Admin functions in a company (sales, HR, billing etc."""
    name = models.CharField(_("Name"), max_length=200, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("name",)


class AdministrativeContact(models.Model):
    """Administrative contact (team or people) of a company."""
    company = models.ForeignKey(Company, verbose_name=_("company"), on_delete=models.CASCADE)
    function = models.ForeignKey(AdministrativeFunction, verbose_name=_("Function"), on_delete=models.CASCADE)
    default_phone = models.CharField(_("Phone Switchboard"), max_length=30, blank=True, null=True)
    default_mail = models.EmailField(_("Generic email"), max_length=100, blank=True, null=True)
    default_fax = models.CharField(_("Generic fax"), max_length=100, blank=True, null=True)
    contact = models.ForeignKey(Contact, blank=True, null=True, verbose_name=_("Contact"), on_delete=models.CASCADE)

    def __str__(self):
        return "%s (%s)" % (str(self.contact), str(self.company))

    def phone(self):
        """Best phone number to use"""
        # Default to phone switch board
        if self.default_phone:
            return self.default_phone
        if self.contact:
            # Use contact phone if defined
            if self.contact.mobile_phone:
                return self.contact.mobile_phone
            elif self.contact.phone:
                return self.contact.phone
        # Bad luck...
        return ""

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
        unique_together = ("company", "contact",)
