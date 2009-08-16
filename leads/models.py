# coding: utf-8
"""
Database access layer.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from django.db import models
from datetime import datetime
from django.db.models import Q

from pydici.leads.utils import send_lead_mail, capitalize, compact_text
import pydici.settings

COMPANY=(
             ("NEWARCH",     "New'Arch"),
             ("SOLUCOM",     "Solucom"),
             ("IDESYS",      "Idesys"),
             ("VISTALI",     "Vistali"),
             ("DREAMSOFT",   "DreamSoft"),
             ("ARCOME",      "Arcome"),
             ("COSMOSBAY",   "CosmosBay~Vectis"),
             ("KLC",         "KLC")
            )

SHORT_DATETIME_FORMAT="%d/%m/%y %H:%M"

class ClientCompany(models.Model):
    """Client company"""
    name=models.CharField("Nom", max_length=200, unique=True)
    
    def __unicode__(self): return self.name

    class Meta:
        ordering=["name"]

class ClientOrganisation(models.Model):
    """A department in client organization"""
    name=models.CharField("Organisation", max_length=200)
    company=models.ForeignKey(ClientCompany, verbose_name="Entreprise")

    def __unicode__(self): return u"%s : %s " % (self.company, self.name)

    class Meta:
        ordering=["company", "name"]

class ClientContact(models.Model):
    """A contact in client organization"""
    name=models.CharField("Nom", max_length=200, unique=True)
    function=models.CharField("Fonction", max_length=200, blank=True)
    email=models.EmailField(blank=True)
    phone=models.CharField("Téléphone", max_length=30, blank=True)
    
    def __unicode__(self): return self.name

    def save(self, force_insert=False, force_update=False):
        self.name=capitalize(self.name)
        super(ClientContact, self).save(force_insert, force_update)

    class Meta:
        ordering=["name"]

class Client(models.Model):
    """A client organization"""
    organisation=models.ForeignKey(ClientOrganisation)
    contact=models.ForeignKey(ClientContact, blank=True, null=True)
    salesOwner=models.CharField("Propriété commerciale", max_length=30, choices=COMPANY, default="NEWARCH")

    def __unicode__(self):
        if self.contact:
            return u"%s (%s)" % (self.organisation, self.contact)
        else:
            return u"%s" % (self.organisation)

    class Meta:
        ordering = ["organisation", "contact"]

class Consultant(models.Model):
    """A New'Arch consultant"""
    name=models.CharField(max_length=50)
    trigramme=models.CharField(max_length=4, unique=True)
    productive=models.BooleanField("Productif", default=True)
    manager=models.ForeignKey("self")

    def __unicode__(self): return self.name

    def save(self, force_insert=False, force_update=False):
        self.name=capitalize(self.name)
        self.trigramme=self.trigramme.upper()
        super(Consultant, self).save(force_insert, force_update)

    class Meta:
        ordering = ["name",]


class SalesMan(models.Model):
    """A salesman from New'Arch or Solucom"""
    name=models.CharField("Nom", max_length=50)
    trigramme=models.CharField(max_length=4, unique=True)
    company=models.CharField("Société", max_length=30, choices=COMPANY)
    email=models.EmailField(blank=True)
    phone=models.CharField("Téléphone", max_length=30, blank=True)

    def __unicode__(self): return "%s (%s)" % (self.name, self.get_company_display())

    def save(self, force_insert=False, force_update=False):
        self.name=capitalize(self.name)
        self.trigramme=self.trigramme.upper()
        super(SalesMan, self).save(force_insert, force_update)

    class Meta:
        ordering = ["name",]

class LeadManager(models.Manager):
    def active(self):
        return self.get_query_set().exclude(state__in=("LOST", "FORGIVEN", "WIN", "SLEEPING"))

    def passive(self):
        return self.get_query_set().filter(state__in=("LOST", "FORGIVEN", "WIN", "SLEEPING"))

class Lead(models.Model):
    """A commercial lead"""
    STATES=(
            ('QUALIF', u'En cours de qualification'),
            ('WRITE_OFFER', u'Proposition à émettre'),
            ('OFFER_SENT', u'Proposition émise'),
            ('NEGOCATION', u'Négociation en cours'),
            ('WIN', u'Affaire gagnée'),
            ('LOST', u'Affaire perdue'),
            ('FORGIVEN', u'Affaire abandonnée'),
            ('SLEEPING', u'En sommeil'),
           )
    name=models.CharField("Nom", max_length=200)
    description=models.TextField(blank=True)
    salesId=models.CharField("Code A6", max_length=100, blank=True)
    sales=models.IntegerField("CA (k€)", blank=True, null=True)
    salesman=models.ForeignKey(SalesMan, blank=True, null=True, verbose_name="Commercial")
    staffing=models.ManyToManyField(Consultant, blank=True)
    external_staffing=models.CharField("Staffing externe", max_length=300, blank=True)
    responsible=models.ForeignKey(Consultant, related_name="%(class)s_responsible", verbose_name="Responsable", blank=True, null=True)
    start_date=models.DateField("Démarrage", blank=True, null=True)
    due_date=models.DateField("Échéance", blank=True, null=True)
    state=models.CharField("État", max_length=30, choices=STATES)
    client=models.ForeignKey(Client)
    creation_date=models.DateTimeField("Création", default=datetime.now())
    update_date=models.DateTimeField("Mise à jour", auto_now=True)
    send_email=models.BooleanField("Envoyer le lead par mail", default=True)

    objects=LeadManager() # Custom manager that factorise active/passive lead code

    def __unicode__(self):
        return u"%s - %s" % (self.client.organisation, self.name)

    def save(self, force_insert=False, force_update=False):
        self.description=compact_text(self.description)
        super(Lead, self).save(force_insert, force_update)

    def staffing_list(self):
        staffing=""
        if self.staffing:
            staffing+=", ".join(x["trigramme"] for x in self.staffing.values())
        if self.external_staffing:
            staffing+=", (%s)" % self.external_staffing
        return staffing

    def update_date_strf(self):
        return self.update_date.strftime(SHORT_DATETIME_FORMAT)
    update_date_strf.short_description="Mise à jour"

    def short_description(self):
        max_length=20
        if len(self.description)>max_length:
            return self.description[:max_length]+"..."
        else:
            return self.description
    short_description.short_description="Description"

    def get_absolute_url(self):
        return "%s/leads/%s/" % (pydici.settings.LEADS_WEB_LINK_ROOT, self.id)

    class Meta:
        ordering=["client__organisation__company__name", "name"]

class Mission(models.Model):
    MISSION_NATURE=(
            ('PROD', u'Productif'),
            ('NONPROD', u'Non productif'),
            ('HOLIDAYS', u'Congés'))
    PROBABILITY=(
            (0,   u"Nulle"),
            (25,  u"Faible"),
            (50,  u"Normale"),
            (75,  u"Forte"),
            (100, u"Certaine"))
    lead=models.ForeignKey(Lead, null=True, blank=True)
    description=models.CharField("Description", max_length=30, blank=True, null=True)
    nature=models.CharField("Type", max_length=30, choices=MISSION_NATURE, default="PROD")
    active=models.BooleanField("Active", default=True)
    probability=models.IntegerField("Proba", default=50, choices=PROBABILITY)
    update_date=models.DateTimeField("Mise à jour", auto_now=True)

    def __unicode__(self):
        if self.description:
            return unicode(self.description)
        else:
            return unicode(self.lead)

    class Meta:
        ordering=["nature", "lead__client__organisation__company", "description"]

class Holiday(models.Model):
    """List of public and enterprise specific holidays"""
    day=models.DateField("date")
    description=models.CharField("Description", max_length=200)

class Staffing(models.Model):
    """The staffing fact table: charge per month per consultant per mission"""
    consultant=models.ForeignKey(Consultant)
    mission=models.ForeignKey(Mission, limit_choices_to=Q(active=True))
    staffing_date=models.DateField("Date")
    charge=models.FloatField("Charge", default=0)
    comment=models.CharField("Remarques", max_length=500, blank=True, null=True)
    update_date=models.DateTimeField("Mise à jour")
    last_user=models.CharField(max_length=60)

    def __unicode__(self):
        return "%s/%s (%s): %s" % (self.staffing_date.month, self.staffing_date.year, self.consultant.trigramme, self.charge)

    def save(self, force_insert=False, force_update=False):
        self.staffing_date=datetime(self.staffing_date.year, self.staffing_date.month, 1)
        super(Staffing, self).save(force_insert, force_update)

    class Meta:
        unique_together = (("consultant", "mission", "staffing_date"),)
        ordering=["staffing_date", "consultant"]
