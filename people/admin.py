# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from people.models import SalesMan, Consultant, ConsultantProfile, RateObjective
from people.forms import ConsultantForm
from core.admin import ReturnToAppAdmin


class SalesManAdmin(ReturnToAppAdmin):
    list_display = ("name", "company", "trigramme", "email", "phone", "active")
    odering = ("name")
    list_filter = ["active", ]
    search_fields = ["name", "trigramme"]
    actions = None


class ConsultantAdmin(ReturnToAppAdmin):
    list_display = ("name", "trigramme", "profil", "productive", "active", "subcontractor")
    search_fields = ("name", "trigramme")
    ordering = ("name",)
    list_filter = ["profil", "productive", "active", "subcontractor"]
    actions = None
    fieldsets = [
        (None, {"fields": ["name", "trigramme", "active", "productive", "company", "profil", "manager", "staffing_manager", "telegram_alias"]}),
        (_("For subcontractors"), {"fields": ["subcontractor", "subcontractor_company"]}),
        ]


class ConsultantProfileAdmin(ReturnToAppAdmin):
    ordering = ("level",)
    list_display = ("name", "level")
    actions = None


class RateObjectiveAdmin(ReturnToAppAdmin):
    ordering = ("start_date",)
    list_display = ("start_date", "consultant", "rate", "rate_type")
    list_filter = ("rate_type", "consultant",)
    date_hierarchy = "start_date"
    actions = None


admin.site.register(Consultant, ConsultantAdmin)
admin.site.register(SalesMan, SalesManAdmin)
admin.site.register(ConsultantProfile, ConsultantProfileAdmin)
admin.site.register(RateObjective, RateObjectiveAdmin)
