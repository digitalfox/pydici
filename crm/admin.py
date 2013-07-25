# coding:utf-8
"""
Django administration setup for pydici CRM module
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib import admin

from crm.models import Client, ClientOrganisation, Company, \
                              Contact, BusinessBroker, Subsidiary, \
                              Supplier, AdministrativeFunction, AdministrativeContact, \
                              MissionContact
from core.admin import ReturnToAppAdmin


class SubsidiaryAdmin(ReturnToAppAdmin):
    """Admin model for subsidiary"""
    list_display = ("name", "code")
    search_fields = ("name", "code")
    ordering = ("name",)


class CompanyAdmin(ReturnToAppAdmin):
    """Admin model for client companies and suppliers companies"""
    list_display = ("name", "code", "businessOwner")
    search_fields = ("name", "code", "businessOwner")
    list_filter = ("businessOwner",)
    ordering = ("name",)


class ContactAdmin(ReturnToAppAdmin):
    list_display = ("name", "companies", "function", "email", "phone", "mobile_phone", "fax")
    odering = ("name",)
    search_fields = ["name", "email", "function", "client__organisation__company__name",
                     "client__organisation__name"]


class BusinessBrokerAdmin(ReturnToAppAdmin):
    list_display = ("company", "contact")
    odering = ("company", "contact")
    search_fields = ["company__name", "contact__name"]


class SupplierAdmin(ReturnToAppAdmin):
    list_display = ("company", "contact")
    odering = ("company", "contact")
    search_fields = ["company__name", "contact__name"]


class AdministrativeFunctionAdmin(ReturnToAppAdmin):
    list_display = ("name",)


class AdministrativeContactAdmin(ReturnToAppAdmin):
    list_display = ("company", "function", "contact", "phone")
    list_display_links = ("company", "function", "contact")
    list_filter = ["function", ]


class MissionContactAdmin(ReturnToAppAdmin):
    list_display = ("company", "contact")
    odering = ("company", "contact")
    search_fields = ["company__name", "contact__name"]


class ClientOrganisationAdmin(ReturnToAppAdmin):
    fieldsets = [(None, {"fields": ["company", "name"]}), ]
    list_display = ("company", "name",)
    list_display_links = ("company", "name",)
    ordering = ("name",)
    search_fields = ("name",)


class ClientOrganisationAdminInline(admin.TabularInline):
    model = ClientOrganisation


class ClientAdmin(ReturnToAppAdmin):
    list_display = ("organisation", "contact")
    ordering = ("organisation",)
    search_fields = ("organisation__company__name", "organisation__name", "contact__name")


admin.site.register(Subsidiary, SubsidiaryAdmin)
admin.site.register(Company, CompanyAdmin)
admin.site.register(Client, ClientAdmin)
admin.site.register(ClientOrganisation, ClientOrganisationAdmin)
admin.site.register(Contact, ContactAdmin)
admin.site.register(BusinessBroker, BusinessBrokerAdmin)
admin.site.register(Supplier, SupplierAdmin)
admin.site.register(AdministrativeFunction, AdministrativeFunctionAdmin)
admin.site.register(AdministrativeContact, AdministrativeContactAdmin)
admin.site.register(MissionContact, MissionContactAdmin)
