# coding: utf-8
"""
Database access layer for pydici CRM module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta

from django.db import models
from django.db.models import Sum, Q, get_model
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.core import urlresolvers
from django.utils.safestring import mark_safe


from core.utils import GEdge, GEdges, GNode, GNodes, cacheable

SHORT_DATETIME_FORMAT = "%d/%m/%y %H:%M"


class AbstractCompany(models.Model):
    """Abstract Company base class for subsidiary, client/supplier/broker/.. company"""
    name = models.CharField(_("Name"), max_length=200, unique=True)
    code = models.CharField(_("Code"), max_length=3, unique=True)
    web = models.URLField(blank=True, null=True)
    street = models.TextField(_("Street"), blank=True, null=True)
    city = models.CharField(_("City"), max_length=200, blank=True, null=True)
    zipcode = models.CharField(_("Zip code"), max_length=30, blank=True, null=True)
    country = models.CharField(_("Country"), max_length=50, blank=True, null=True)
    billing_street = models.TextField(_("Street"), blank=True, null=True)
    billing_city = models.CharField(_("City"), max_length=200, blank=True, null=True)
    billing_zipcode = models.CharField(_("Zip code"), max_length=30, blank=True, null=True)
    billing_country = models.CharField(_("Country"), max_length=50, blank=True, null=True)

    def __unicode__(self):
        return unicode(self.name)

    def main_address(self):
        return "%s\n%s %s\n%s" % (self.street, self.zipcode, self.city, self.country)

    def billing_address(self):
        return "%s\n%s %s\n%s" % (self.billing_street, self.billing_zipcode, self.billing_city, self.billing_country)

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
    businessOwner = models.ForeignKey("people.Consultant", verbose_name=_("Business owner"), related_name="%(class)s_business_owner", null=True)
    external_id = models.CharField(max_length=200, blank=True, null=True, unique=True, default=None)

    def sales(self, onlyLastYear=False):
        """Sales billed for this company in keuros"""
        from billing.models import ClientBill
        data = ClientBill.objects.filter(lead__client__organisation__company=self)
        if onlyLastYear:
            data = data.filter(creation_date__gt=(date.today() - timedelta(365)))
        if data.count():
            return float(data.aggregate(Sum("amount")).values()[0]) / 1000
        else:
            return 0

    def supplier_billing(self, onlyLastYear=False):
        """Supplier billing for this company in keuros"""
        from billing.models import SupplierBill
        data = SupplierBill.objects.filter(lead__client__organisation__company=self)
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

    def __unicode__(self):
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
                return mark_safe(u"<a href='%s'>%s</a>" % (urlresolvers.reverse("crm.views.company_detail", args=[companies[0].id,]), unicode(companies[0])))
            else:
                return companies[0]
        elif companies_count > 1:
            if html:
                return mark_safe(u", ".join([u"<a href='%s'>%s</a>" % (urlresolvers.reverse("crm.views.company_detail", args=[i.id,]), unicode(i)) for i in companies]))
            else:
                return u", ".join([unicode(i) for i in companies])
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
            me = GNode(unicode(self.id), unicode(self), color="#EEE")
            nodes.add(me)
            # Mission relations
            for missionContact in self.missioncontact_set.all():
                for mission in missionContact.mission_set.all():
                    missionNode = GNode("mission-%s" % mission.id, """<span class='glyphicon-svg glyphicon-cog'></span>
                                                                      <span class='graph-tooltip' title='%s'><a href='%s'>&nbsp;%s&nbsp;</a></span>""" % (mission.short_name(),
                                                                                                                                                          mission.get_absolute_url(),
                                                                                                                                                          mission.mission_id()))
                    nodes.add(missionNode)
                    edges.append(GEdge(me, missionNode, color=missionColor))
                    for consultant in mission.consultants():
                        consultantNode = GNode("consultant-%s" % consultant.id, unicode(consultant))
                        nodes.add(consultantNode)
                        edges.append(GEdge(missionNode, consultantNode, color=missionColor))
            # Business / Lead relations
            for client in self.client_set.all():
                if client.lead_set.count() < 5 :
                    for lead in client.lead_set.all():
                        leadNode = GNode("lead-%s" % lead.id, """<span class="glyphicon-svg glyphicon-euro"></span>
                                                                 <span class='graph-tooltip' title='%s'><a href='%s'>%s&nbsp;</a></span>""" % (unicode(lead),
                                                                                                                                               lead.get_absolute_url(),
                                                                                                                                               lead.deal_id))
                        nodes.add(leadNode)
                        edges.append(GEdge(me,leadNode, color=leadColor))
                        if lead.responsible:
                            consultantNode = GNode("consultant-%s" % lead.responsible.id, unicode(lead.responsible))
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
                    leadsId = "-".join([unicode(l.id) for l in leads])
                    leadsTitle = unicode(client.organisation)
                    leadsLabel = _("%s leads" % len(leads))
                    leadsNode = GNode("leads-%s" % leadsId, """<span class='glyphicon-svg glyphicon-euro'></span>
                                                               <span class='graph-tooltip' title='%s'>&nbsp;%s&nbsp;</span>""" % (leadsTitle, leadsLabel))
                    nodes.add(leadsNode)
                    edges.append(GEdge(me,leadsNode, color=leadColor))
                    for responsible in responsibles:
                        consultantNode = GNode("consultant-%s" % responsible.id, unicode(responsible))
                        nodes.add(consultantNode)
                        edges.append(GEdge(leadsNode, consultantNode, color=leadColor))

            # Direct contact relation
            for consultant in self.contact_points.all():
                consultantNode = GNode("consultant-%s" % consultant.id, unicode(consultant))
                nodes.add(consultantNode)
                edges.append(GEdge(me, consultantNode, color=directColor))

            return """var nodes=%s; var edges=%s;""" % (nodes.dump(), edges.dump())

        except Exception, e:
            print e

    def get_absolute_url(self):
        return urlresolvers.reverse("contact_detail", args=[self.id, ])

    class Meta:
        ordering = ["name"]


class BusinessBroker(models.Model):
    """A business broken: someone that is not a client but an outsider that act
    as a partner to provide some business"""
    company = models.ForeignKey(Company, verbose_name=_("Broker company"))
    contact = models.ForeignKey(Contact, blank=True, null=True, verbose_name=_("Contact"), on_delete=models.SET_NULL)

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
        unique_together = (("company", "contact",))


class Supplier(models.Model):
    """A supplier is defined by a contact and the supplier company where he works at the moment"""
    company = models.ForeignKey(Company, verbose_name=_("Supplier company"))
    contact = models.ForeignKey(Contact, blank=True, null=True, verbose_name=_("Contact"), on_delete=models.SET_NULL)

    def __unicode__(self):
        if self.contact:
            return u"%s (%s)" % (self.company, self.contact)
        else:
            return unicode(self.company)

    class Meta:
        ordering = ["company", "contact"]
        verbose_name = _("Supplier")
        unique_together = (("company", "contact",))


class Client(models.Model):
    """A client is defined by a contact and the organisation where he works at the moment"""
    EXPECTATIONS = (
            ('1_NONE', ugettext("None")),
            ('2_DECREASING', ugettext("Decreasing")),
            ('3_FLAT', ugettext("Flat")),
            ('4_INCREASING', ugettext("Increasing")),
           )
    ALIGNMENT = (
            ("1_RESTRAIN", ugettext("To restrain")),
            ("2_STANDARD", ugettext("Standard")),
            ("3_STRATEGIC", ugettext("Strategic")),
                 )
    organisation = models.ForeignKey(ClientOrganisation, verbose_name=_("Company : Organisation"))
    contact = models.ForeignKey(Contact, blank=True, null=True, verbose_name=_("Contact"), on_delete=models.SET_NULL)
    expectations = models.CharField(max_length=30, choices=EXPECTATIONS, default=EXPECTATIONS[2][0], verbose_name=_("Expectations"))
    alignment = models.CharField(max_length=30, choices=ALIGNMENT, default=ALIGNMENT[1][0], verbose_name=_("Strategic alignment"))
    active = models.BooleanField(_("Active"), default=True)

    def __unicode__(self):
        if self.contact:
            return u"%s (%s)" % (self.organisation, self.contact)
        else:
            return unicode(self.organisation)

    def getFinancialConditions(self):
        """Get financial condition for this client by profil
        @return: ((profil1, avgrate1), (profil2, avgrate2)...)"""
        FinancialCondition = get_model("staffing", "FinancialCondition")
        ConsultantProfile = get_model("people", "ConsultantProfile")
        data = {}
        rates = []

        for profil in ConsultantProfile.objects.all():
            data[profil] = []

        #for profil in ConsultantProfile
        for fc in FinancialCondition.objects.filter(mission__lead__client=self,
                                               consultant__timesheet__charge__gt=0,  # exclude null charge
                                               consultant__timesheet=models.F("mission__timesheet")  # Join to avoid duplicate entries
                                               ).select_related():
            data[fc.consultant.profil].append(fc.daily_rate)

        # compute average
        for profil, profilRates in data.items():
            if len(profilRates) > 0:
                avg = sum(profilRates) / len(profilRates)
            else:
                avg = None
            rates.append((profil, avg))

        # Sort by profil
        rates.sort(key=lambda x: x[0].level)
        return rates

    @cacheable("Client__objectiveMargin__%(id)s", 60)
    def objectiveMargin(self):
        """Compute margin over budget objective across all mission of this client
        @return: list of (margin in €, margin in % of total turnover) for internal consultant and subcontractor"""
        Mission = get_model("staffing", "Mission")  # Get Mission with get_model to avoid circular imports
        consultantMargin = 0
        subcontractorMargin = 0

        for mission in Mission.objects.filter(lead__client=self):
            for consultant, margin in mission.objectiveMargin().items():
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
        return ((consultantMargin, consultantMargin_pc), (subcontractorMargin, subcontractorMargin_pc))

    def fixedPriceMissionMargin(self):
        """Compute total fixed price margin in €  mission for this client. Only finished mission (ie archived) are
        considered"""
        Mission = get_model("staffing", "Mission")  # Get Mission with get_model to avoid circular imports
        margin = 0
        missions = Mission.objects.filter(lead__client=self, active=False,
                                          lead__state = "WON", billing_mode="FIXED_PRICE")
        for mission in missions:
            margin += mission.margin()
        return margin * 1000

    def sales(self, onlyLastYear=False):
        """Sales billed for this client in keuros"""
        from billing.models import ClientBill
        data = ClientBill.objects.filter(lead__client=self)
        if onlyLastYear:
            data = data.filter(creation_date__gt=(date.today() - timedelta(365)))
        if data.count():
            return float(data.aggregate(Sum("amount")).values()[0]) / 1000
        else:
            return 0

    def getActiveLeads(self):
        """@return: list (qs) of active leads for this client"""
        return self.lead_set.exclude(state__in=(("LOST", "FORGIVEN", "SLEEPING")))

    def getActiveMissions(self):
        """@return: list of active missions for this client"""
        missions = list()
        for lead in self.getActiveLeads():
            missions.extend(lead.mission_set.filter(active=True))
        return missions

    def get_absolute_url(self):
        return urlresolvers.reverse("company_detail", args=[self.organisation.company.id, ])

    class Meta:
        ordering = ["organisation", "contact"]
        verbose_name = _("Client")
        unique_together = (("organisation", "contact",))


class MissionContact(models.Model):
    """Contact encountered during mission"""
    company = models.ForeignKey(Company, verbose_name=_("company"))
    contact = models.ForeignKey(Contact, verbose_name=_("Contact"))

    def __unicode__(self):
        return u"%s (%s)" % (self.contact, self.company)

    def get_absolute_url(self):
        return urlresolvers.reverse("contact_detail", args=[self.contact.id, ])


    class Meta:
        ordering = ["company", "contact"]
        verbose_name = _("Mission contact")
        unique_together = (("company", "contact",))


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
        unique_together = (("company", "contact",))
