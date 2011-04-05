# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django.contrib import admin

from pydici.staffing.models import Mission, Holiday, Timesheet, FinancialCondition
from pydici.staffing.forms import MissionAdminForm

class MissionAdmin(admin.ModelAdmin):
    list_display = ("lead", "description", "nature", "probability", "mission_id", "active", "update_date")
    search_fields = ("lead__name", "description", "deal_id", "lead__client__organisation__company__name",
                   "lead__client__contact__name")
    ordering = ("lead", "description")
    date_hierarchy = "update_date"
    list_filter = ["nature", "probability", "active"]
    actions = None
    form = MissionAdminForm


class HolidayAdmin(admin.ModelAdmin):
    list_display = ("day", "description")
    date_hierarchy = "day"
    actions = None

class FinancialConditionAdmin(admin.ModelAdmin):
    list_display = ("mission", "consultant", "daily_rate")
    search_fileds = ("mission__lead__name", "mission__description", "mission__deal_id", "mission__lead__client__organisation__company__name",
                   "mission__lead__client__contact__name", "consultant__name", "consultant__trigramme")
    actions = None

admin.site.register(Mission, MissionAdmin)
admin.site.register(Holiday, HolidayAdmin)
admin.site.register(FinancialCondition, FinancialConditionAdmin)
admin.site.register(Timesheet)
