# coding:utf-8
"""
Django administration setup for pydici CRM module
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib import admin

from pydici.crm.models import Client, ClientOrganisation, Company, \
                              Contact, BusinessBroker, Subsidiary, \
                              Supplier


class CompanyAdmin(admin.ModelAdmin):
    """Base admin model for subsidiary, clientcompanies and suppliers companies"""
    list_display = ("name", "code")
    search_fields = ("name", "code")
    ordering = ("name",)
    actions = None


class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "companies", "function", "email", "phone", "mobile_phone", "fax")
    odering = ("name",)
    search_fields = ["name", "email", "function", "client__organisation__company__name",
                     "client__organisation__name"]
    actions = None


class BusinessBrokerAdmin(admin.ModelAdmin):
    list_display = ("company", "contact")
    odering = ("company", "contact")
    search_fields = ["company", "contact__name"]
    actions = None


class ClientOrganisationAdmin(admin.ModelAdmin):
    fieldsets = [(None, {"fields": ["company", "name"]}), ]
    list_display = ("company", "name",)
    list_display_links = ("company", "name",)
    ordering = ("name",)
    search_fields = ("name",)
    actions = None


class ClientOrganisationAdminInline(admin.TabularInline):
    model = ClientOrganisation


class ClientAdmin(admin.ModelAdmin):
    list_display = ("organisation", "salesOwner", "contact")
    ordering = ("organisation",)
    search_fields = ("organisation__company__name", "organisation__name", "contact__name")
    actions = None


admin.site.register(Subsidiary, CompanyAdmin)
admin.site.register(Company, CompanyAdmin)
admin.site.register(Client, ClientAdmin)
admin.site.register(ClientOrganisation, ClientOrganisationAdmin)
admin.site.register(Contact, ContactAdmin)
admin.site.register(BusinessBroker, BusinessBrokerAdmin)
