# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext

from pydici.people.models import SalesMan, Consultant, ConsultantProfile

class SalesManAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "trigramme", "email", "phone")
    odering = ("name")
    search_fields = ["name", "trigramme"]
    actions = None


class ConsultantAdmin(admin.ModelAdmin):
    list_display = ("name", "trigramme", "profil", "productive", "active")
    search_fields = ("name", "trigramme")
    ordering = ("name",)
    list_filter = ["profil", "productive", "active"]
    actions = None

class ConsultantProfileAdmin(admin.ModelAdmin):
    ordering = ("level",)
    list_display = ("name", "level")
    actions = None

admin.site.register(Consultant, ConsultantAdmin)
admin.site.register(SalesMan, SalesManAdmin)
admin.site.register(ConsultantProfile, ConsultantProfileAdmin)
