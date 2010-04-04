# coding: utf-8
"""
Database access layer.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from django.db import models
from datetime import datetime
from django.db.models import Q
from django.core.cache import cache
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext

from pydici.leads.utils import send_lead_mail, capitalize, compact_text
import pydici.settings


SHORT_DATETIME_FORMAT = "%d/%m/%y %H:%M"

class Subsidiary(models.Model):
    """Internal company / organisation unit"""
    name = models.CharField(_("Name"), max_length=200, unique=True)

    def __unicode__(self): return self.name

    class Meta:
        verbose_name = _("Subsidiary")
        verbose_name_plural = _("Subsidiaries")

class ConsultantProfile(models.Model):
    """Consultant hierarchy"""
    name = models.CharField(_("Name"), max_length=50, unique=True)
    level = models.IntegerField(_("Level"))

    def __unicode__(self): return self.name

    class Meta:
        ordering = ["level"]
        verbose_name = _("Consultant profile")

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

class Consultant(models.Model):
    """A consultant that can manage a lead or be ressource of a mission"""
    name = models.CharField(max_length=50)
    trigramme = models.CharField(max_length=4, unique=True)
    company = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"))
    productive = models.BooleanField(_("Productive"), default=True)
    manager = models.ForeignKey("self", null=True, blank=True)
    profil = models.ForeignKey(ConsultantProfile, verbose_name=_("Profil"))

    def __unicode__(self): return self.name

    def save(self, force_insert=False, force_update=False):
        self.name = capitalize(self.name)
        self.trigramme = self.trigramme.upper()
        super(Consultant, self).save(force_insert, force_update)

    class Meta:
        ordering = ["name", ]
        verbose_name = _("Consultant")


class SalesMan(models.Model):
    """A salesman"""
    name = models.CharField(_("Name"), max_length=50)
    trigramme = models.CharField(max_length=4, unique=True)
    company = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"))
    email = models.EmailField(blank=True)
    phone = models.CharField(_("Phone"), max_length=30, blank=True)

    def __unicode__(self): return "%s (%s)" % (self.name, self.get_company_display())

    def save(self, force_insert=False, force_update=False):
        self.name = capitalize(self.name)
        self.trigramme = self.trigramme.upper()
        super(SalesMan, self).save(force_insert, force_update)

    class Meta:
        ordering = ["name", ]
        verbose_name = _("Salesman")
        verbose_name_plural = _("Salesmen")

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
    send_email = models.BooleanField(_("Send lead by email"), default=False)

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

    def get_absolute_url(self):
        return "%s/leads/%s/" % (pydici.settings.LEADS_WEB_LINK_ROOT, self.id)

    class Meta:
        ordering = ["client__organisation__company__name", "name"]
        verbose_name = _("Lead")

class Mission(models.Model):
    MISSION_NATURE = (
            ('PROD', _("Productive")),
            ('NONPROD', _("Unproductive")),
            ('HOLIDAYS', _("Holidays")))
    PROBABILITY = (
            (0, _("Null")),
            (25, _("Low")),
            (50, _("Normal")),
            (75, _("High")),
            (100, _("Certain")))
    lead = models.ForeignKey(Lead, null=True, blank=True, verbose_name=_("Lead"))
    deal_id = models.CharField(_("Deal id"), max_length=100, blank=True)
    description = models.CharField(_("Description"), max_length=30, blank=True, null=True)
    nature = models.CharField(_("Type"), max_length=30, choices=MISSION_NATURE, default="PROD")
    active = models.BooleanField(_("Active"), default=True)
    probability = models.IntegerField(_("Proba"), default=50, choices=PROBABILITY)
    update_date = models.DateTimeField(_("Updated"), auto_now=True)

    def __unicode__(self):
        if self.description:
            return unicode(self.description)
        else:
            # As lead name computation generate lots of sql request, cache it to avoid
            # perf issue for screen that intensively use lead name (like consultant staffing)
            name = cache.get("missionName-%s" % self.id)
            if not name:
                name = unicode(self.lead)
                cache.set("missionName-%s" % self.id, name, 3)
            return name

    def short_name(self):
        """Client name if defined, else first words of description"""
        if self.lead:
            return unicode(self.lead.client.organisation.company)
        else:
            return self.description.split(":")[0]

    def no_more_staffing_since(self, refDate=datetime.now()):
        """@return: True if at least one staffing is defined after refDate. Zero charge staffing are considered."""
        return not bool(self.staffing_set.filter(staffing_date__gt=refDate).count())

    class Meta:
        ordering = ["nature", "lead__client__organisation__company", "description"]
        verbose_name = _("Mission")

class Holiday(models.Model):
    """List of public and enterprise specific holidays"""
    day = models.DateField(_("Date"))
    description = models.CharField(_("Description"), max_length=200)

    class Meta:
        verbose_name = _("Holiday")

class Staffing(models.Model):
    """The staffing fact table: charge per month per consultant per mission"""
    consultant = models.ForeignKey(Consultant)
    mission = models.ForeignKey(Mission, limit_choices_to=Q(active=True))
    staffing_date = models.DateField(_("Date"))
    charge = models.FloatField(_("Load"), default=0)
    comment = models.CharField(_("Comments"), max_length=500, blank=True, null=True)
    update_date = models.DateTimeField(blank=True, null=True)
    last_user = models.CharField(max_length=60, blank=True, null=True)

    def __unicode__(self):
        return "%s/%s (%s): %s" % (self.staffing_date.month, self.staffing_date.year, self.consultant.trigramme, self.charge)

    def save(self, force_insert=False, force_update=False):
        self.staffing_date = datetime(self.staffing_date.year, self.staffing_date.month, 1)
        super(Staffing, self).save(force_insert, force_update)

    class Meta:
        unique_together = (("consultant", "mission", "staffing_date"),)
        ordering = ["staffing_date", "consultant"]
        verbose_name = _("Staffing")
