# coding:utf-8
"""
Django administration setup for pydici CRM module
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib import admin

from pydici.crm.models import Client, ClientOrganisation, ClientCompany, \
                              ClientContact, BusinessBroker

class ClientContactAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "function", "email", "phone", "mobile_phone", "fax")
    odering = ("name",)
    search_fields = ["name", "email", "function", "client__organisation__company__name",
                     "client__organisation__name"]
    actions = None

class BusinessBrokerAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "company", "email", "phone", "mobile_phone")
    odering = ("name")
    search_fields = ["name", "code", "company"]
    actions = None


class ClientOrganisationAdmin(admin.ModelAdmin):
    fieldsets = [(None, {"fields": ["company", "name"] }), ]
    list_display = ("company", "name",)
    list_display_links = ("company", "name",)
    ordering = ("name",)
    search_fields = ("name",)
    actions = None

class ClientOrganisationAdminInline(admin.TabularInline):
    model = ClientOrganisation

class ClientCompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    ordering = ("name",)
    search_fields = ("name", "code")
    actions = None

class ClientAdmin(admin.ModelAdmin):
    list_display = ("organisation", "salesOwner", "contact")
    ordering = ("organisation",)
    search_fields = ("organisation__company__name", "organisation__name", "contact__name")
    actions = None

admin.site.register(Client, ClientAdmin)
admin.site.register(ClientOrganisation, ClientOrganisationAdmin)
admin.site.register(ClientCompany, ClientCompanyAdmin)
admin.site.register(ClientContact, ClientContactAdmin)
admin.site.register(BusinessBroker, BusinessBrokerAdmin)
