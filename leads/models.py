# coding: utf-8
from django.db import models
from django.contrib import admin
from datetime import datetime

from pydici.leads.utils import send_lead_mail

COMPANY=(
             ("NEWARCH",     "New'Arch"),
             ("SOLUCOM/D2S", "Solucom/D²S"),
             ("SOLUCOM/SEC", "Solucom/Sec"),
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
    name=models.CharField("Nom", max_length=200)
    
    def __unicode__(self): return self.name

class ClientOrganisation(models.Model):
    """A department in client organization"""
    name=models.CharField("Organisation", max_length=200)
    company=models.ForeignKey(ClientCompany, verbose_name="Entreprise")

    def __unicode__(self): return u"%s : %s " % (self.company, self.name)

class ClientContact(models.Model):
    """A contact in client organization"""
    name=models.CharField("Nom", max_length=200)
    function=models.CharField("Fonction", max_length=200, blank=True)
    email=models.EmailField(blank=True)
    phone=models.CharField("Téléphone", max_length=30, blank=True)
    
    def __unicode__(self): return self.name

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

class Consultant(models.Model):
    """A New'Arch consultant"""
    name=models.CharField(max_length=50)
    trigramme=models.CharField(max_length=4, unique=True)
    #manager=models.ForeignKey(Consultant)

    def __unicode__(self): return self.name

class SalesMan(models.Model):
    """A salesman from New'Arch or Solucom"""
    name=models.CharField("Nom", max_length=50)
    trigramme=models.CharField(max_length=4)
    company=models.CharField("Société", max_length=30, choices=COMPANY)
    email=models.EmailField(blank=True)
    phone=models.CharField("Téléphone", max_length=30, blank=True)

    def __unicode__(self): return "%s (%s)" % (self.name, self.get_company_display())

class LeadManager(models.Manager):
    def active(self):
        return self.get_query_set().exclude(state__in=("LOST", "FORGIVEN", "WIN"))

    def passive(self):
        return self.get_query_set().filter(state__in=("LOST", "FORGIVEN", "WIN"))

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

class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "client", "description", "responsible", "salesman", "sales", "state", "due_date", "update_date")
    fieldsets = [
        (None,    {"fields": ["name", "client", "description", "salesId"]}),
        ('État et suivi',     {'fields': ['responsible', 'salesman', 'start_date', 'state', 'due_date']}),
        ('Staffing',     {'fields': ["staffing", "external_staffing", "sales"]}),
        ]
    ordering = ("creation_date",)
    filter_horizontal=["staffing"]
    list_filter = ["state",]
    date_hierarchy = "creation_date"
    search_fields = ["name", "description", "salesId",
                     "responsible__name",  "responsible__trigramme",
                     "salesman__name", "salesman__trigramme",
                     "client__contact__name", "client__organisation__company__name"]

    def save_model(self, request, obj, form, change):
        obj.save()
        if not change:
            try:
                send_lead_mail(obj)
                request.user.message_set.create(message="Ce lead a été envoyé par mail au plan de charge.")
            except Exception, e:
                request.user.message_set.create(message="Échec d'envoi du mail : %s" % e)

class ClientContactAdmin(admin.ModelAdmin):
    list_display=("name", "function", "email", "phone")
    odering=("name")
    search_fields=["name", "function"]

class SalesManAdmin(admin.ModelAdmin):
    list_display=("name", "company", "trigramme", "email", "phone")
    odering=("name")
    search_fields=["name", "trigramme"]

class ClientOrganisationAdmin(admin.ModelAdmin):
    fieldsets=[(None,    {"fields": ["company", "name"] } ),]
    list_display=("name",)
    ordering=("name",)
    search_fields=("name",)

class ClientOrganisationAdminInline(admin.TabularInline):
    model=ClientOrganisation

class ClientCompanyAdmin(admin.ModelAdmin):
    list_display=("name",)
    ordering=("name",)
    search_fields=("name",)

    inlines=[ClientOrganisationAdminInline,]

class ClientAdmin(admin.ModelAdmin):
    list_display=("organisation", "salesOwner", "contact")
    ordering=("organisation",)
    search_fields=("organisation__company__name", "organisation__name", "contact__name")

admin.site.register(Lead, LeadAdmin)
admin.site.register(Client, ClientAdmin)
admin.site.register(ClientOrganisation, ClientOrganisationAdmin)
admin.site.register(ClientCompany, ClientCompanyAdmin)
admin.site.register(ClientContact, ClientContactAdmin)
admin.site.register(Consultant)
admin.site.register(SalesMan, SalesManAdmin)