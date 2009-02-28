# coding: utf-8
"""
Database access layer.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: BSD
"""

from django.db import models
from datetime import datetime

from pydici.leads.utils import send_lead_mail, capitalize
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
    #manager=models.ForeignKey(Consultant)

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

    objects=LeadManager() # Custom manager that factorise active/passive lead code

    def __unicode__(self):
        return u"%s (%s)" % (self.name, self.client)

    def staffing_list(self):
        return ", ".join(x["trigramme"] for x in self.staffing.values() ) +", %s" % self.external_staffing

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

    def get_next_active(self):
        """Return next active lead"""
        return self.get_next_by_creation_date(state__in=("QUALIF", "WRITE_OFFER", "OFFER_SENT", "NEGOCATION"))

    def get_previous_active(self):
        """Return next active lead"""
        return self.get_previous_by_creation_date(state__in=("QUALIF", "WRITE_OFFER", "OFFER_SENT", "NEGOCATION"))