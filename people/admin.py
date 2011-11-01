# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from pydici.people.models import SalesMan, Consultant, ConsultantProfile
from pydici.people.forms import ConsultantForm

class SalesManAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "trigramme", "email", "phone", "active")
    odering = ("name")
    list_filter = ["active", ]
    search_fields = ["name", "trigramme"]
    actions = None


class ConsultantAdmin(admin.ModelAdmin):
    list_display = ("name", "trigramme", "profil", "productive", "active", "subcontractor")
    search_fields = ("name", "trigramme")
    ordering = ("name",)
    list_filter = ["profil", "productive", "active", "subcontractor"]
    actions = None
    fieldsets = [
        (None, {"fields": ["name", "trigramme", "active", "productive", "company", "profil", "manager"]}),
        (_("For subcontractors"), {"fields": ["subcontractor", "subcontractor_company" ]}),
        ]
    form = ConsultantForm

class ConsultantProfileAdmin(admin.ModelAdmin):
    ordering = ("level",)
    list_display = ("name", "level")
    actions = None

admin.site.register(Consultant, ConsultantAdmin)
admin.site.register(SalesMan, SalesManAdmin)
admin.site.register(ConsultantProfile, ConsultantProfileAdmin)
