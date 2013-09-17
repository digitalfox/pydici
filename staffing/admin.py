# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib import admin

from ajax_select.admin import AjaxSelectAdmin

from staffing.models import Mission, Holiday, Timesheet, FinancialCondition, Staffing
from staffing.forms import MissionAdminForm, FinancialConditionAdminForm
from core.admin import ReturnToAppAdmin


class MissionAdmin(AjaxSelectAdmin, ReturnToAppAdmin):
    list_display = ("lead", "description", "nature", "probability", "mission_id", "subsidiary", "active", "update_date")
    list_display_links = ["lead", "description"]
    search_fields = ("lead__name", "description", "deal_id", "lead__client__organisation__company__name",
                   "lead__client__contact__name")
    ordering = ("lead", "description")
    date_hierarchy = "update_date"
    list_filter = ["nature", "probability", "subsidiary", "active"]

    actions = None
    form = MissionAdminForm


class HolidayAdmin(admin.ModelAdmin):
    list_display = ("day", "description")
    date_hierarchy = "day"
    actions = None


class FinancialConditionAdmin(ReturnToAppAdmin):
    list_display = ("mission", "consultant", "daily_rate")
    search_fileds = ("mission__lead__name", "mission__description", "mission__deal_id", "mission__lead__client__organisation__company__name",
                   "mission__lead__client__contact__name", "consultant__name", "consultant__trigramme")
    actions = None
    form = FinancialConditionAdminForm


admin.site.register(Mission, MissionAdmin)
admin.site.register(Holiday, HolidayAdmin)
admin.site.register(FinancialCondition, FinancialConditionAdmin)
admin.site.register(Timesheet)
admin.site.register(Staffing)
