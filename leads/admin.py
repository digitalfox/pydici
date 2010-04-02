# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from datetime import datetime

from pydici.leads.models import Lead, Client, ClientOrganisation, ClientCompany, ClientContact, Consultant, \
                                SalesMan, Mission, Staffing, Holiday, ConsultantProfile, Subsidiary

from pydici.leads.utils import send_lead_mail, capitalize


class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "client", "short_description", "responsible", "salesman", "state", "due_date", "update_date_strf")
    fieldsets = [
        (None, {"fields": ["name", "client", "description", "action"]}),
        ("État et suivi", {"fields": ["responsible", "salesman", "state", "due_date", "start_date"]}),
        ("Staffing", {"fields": ["staffing", "external_staffing", "sales"]}),
        (None, {"fields": ["send_email", ]})
        ]
    ordering = ("creation_date",)
    filter_horizontal = ["staffing"]
    list_filter = ["state", ]
    date_hierarchy = "update_date"
    search_fields = ["name", "description", "action",
                     "responsible__name", "responsible__trigramme",
                     "salesman__name", "salesman__trigramme",
                     "client__contact__name", "client__organisation__company__name",
                     "client__organisation__name",
                     "staffing__trigramme", "staffing__name"]

    def save_model(self, request, obj, form, change):
        mail = False
        if obj.send_email:
            mail = True
            obj.send_email = False
        obj.save()
        form.save_m2m() # Save many to many relations
        if mail:
            try:
                fromAddr = request.user.email or "noreply@noreply.com"
                send_lead_mail(obj, fromAddr=fromAddr,
                               fromName="%s %s" % (request.user.first_name, request.user.last_name))
                request.user.message_set.create(message=_("Lead sent to business mailing list"))
            except Exception, e:
                request.user.message_set.create(message=_("Failed to send mail: %s") % e)

        # Create or update mission object if needed
        try:
            mission = Mission.objects.get(lead=obj)
            mission_does_not_exist = False
        except Mission.DoesNotExist:
            mission = Mission(lead=obj) # Mission is saved below if needed
            mission_does_not_exist = True

        if obj.state in ("OFFER_SENT", "NEGOCATION", "WIN") and mission_does_not_exist:
            currentMonth = datetime.now()
            mission.lead = obj
            mission.save()
            # Create default staffing
            for consultant in obj.staffing.all():
                staffing = Staffing()
                staffing.mission = mission
                staffing.consultant = consultant
                staffing.staffing_date = currentMonth
                staffing.update_date = currentMonth
                staffing.last_user = "-"
                staffing.save()
            request.user.message_set.create(message=_("A mission has been initialized for this lead."))
        if obj.state == "WIN":
            mission.probability = 100
            mission.active = True
            mission.save()
            request.user.message_set.create(message=_("Mission's probability has been set to 100%"))
        elif obj.state in ("LOST", "FORGIVEN", "SLEEPING"):
            mission.probability = 0
            mission.active = False
            mission.save()
            request.user.message_set.create(message=_("According mission has been archived"))



class ClientContactAdmin(admin.ModelAdmin):
    list_display = ("name", "function", "email", "phone")
    odering = ("name")
    search_fields = ["name", "function"]

class SalesManAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "trigramme", "email", "phone")
    odering = ("name")
    search_fields = ["name", "trigramme"]

class ClientOrganisationAdmin(admin.ModelAdmin):
    fieldsets = [(None, {"fields": ["company", "name"] }), ]
    list_display = ("company", "name",)
    list_display_links = ("company", "name",)
    ordering = ("name",)
    search_fields = ("name",)

class ClientOrganisationAdminInline(admin.TabularInline):
    model = ClientOrganisation

class ClientCompanyAdmin(admin.ModelAdmin):
    list_display = ("name",)
    ordering = ("name",)
    search_fields = ("name",)

class ClientAdmin(admin.ModelAdmin):
    list_display = ("organisation", "salesOwner", "contact")
    ordering = ("organisation",)
    search_fields = ("organisation__company__name", "organisation__name", "contact__name")

class ConsultantAdmin(admin.ModelAdmin):
    list_display = ("name", "trigramme", "profil", "productive")
    search_fields = ("name", "trigramme")
    ordering = ("name",)
    list_filter = ["profil", ]

class MissionAdmin(admin.ModelAdmin):
    list_display = ("lead", "description", "nature", "probability", "deal_id", "active", "update_date")
    search_fields = ("lead__name", "description", "deal_id", "lead__client__organisation__company__name",
                   "lead__client__contact__name")
    ordering = ("lead", "description")
    date_hierarchy = "update_date"
    list_filter = ["nature", "probability", "active"]

class HolidayAdmin(admin.ModelAdmin):
    list_display = ("day", "description")
    date_hierarchy = "day"

class ConsultantProfileAdmin(admin.ModelAdmin):
    ordering = ("level",)
    list_display = ("name", "level")

class SubsidiaryAdmin(admin.ModelAdmin):
    ordering = ("name",)

admin.site.register(Lead, LeadAdmin)
admin.site.register(Client, ClientAdmin)
admin.site.register(ClientOrganisation, ClientOrganisationAdmin)
admin.site.register(ClientCompany, ClientCompanyAdmin)
admin.site.register(ClientContact, ClientContactAdmin)
admin.site.register(Consultant, ConsultantAdmin)
admin.site.register(SalesMan, SalesManAdmin)
admin.site.register(Mission, MissionAdmin)
admin.site.register(Holiday, HolidayAdmin)
admin.site.register(ConsultantProfile, ConsultantProfileAdmin)
admin.site.register(Subsidiary, SubsidiaryAdmin)
