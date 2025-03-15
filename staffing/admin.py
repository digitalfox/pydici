# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib import admin

from staffing.models import Mission, Holiday, Timesheet, FinancialCondition, Staffing, AnalyticCode, MarketingProduct
from core.admin import ReturnToAppAdmin


class AnalyticCodeAdmin(ReturnToAppAdmin):
    list_display = ("code", "description")
    search_fields = list_display
    ordering = ("code",)


class MarketingProductAdmin(ReturnToAppAdmin):
    list_display = ("code", "description", "subsidiary", "active")
    search_fields = ("code", "description")
    list_filter = ("subsidiary", "active")
    ordering = ("subsidiary", "code",)


class MissionAdmin(ReturnToAppAdmin):
    list_display = ("lead", "description", "nature", "probability", "mission_id", "subsidiary", "active", "analytic_code", "update_date")
    list_display_links = ["lead", "description"]
    search_fields = ("lead__name", "description", "deal_id", "lead__client__organisation__company__name",
                     "lead__client__contact__name")
    ordering = ("lead", "description")
    date_hierarchy = "update_date"
    list_filter = ["nature", "probability", "subsidiary", "active", "archived_date"]
    actions = None
    fields = ("lead", "description", "nature", "probability", "deal_id", "subsidiary", "analytic_code", "marketing_product", "active")


class HolidayAdmin(admin.ModelAdmin):
    list_display = ("day", "description")
    date_hierarchy = "day"
    actions = None


class FinancialConditionAdmin(ReturnToAppAdmin):
    list_display = ("mission", "consultant", "daily_rate")
    search_fileds = ("mission__lead__name", "mission__description", "mission__deal_id", "mission__lead__client__organisation__company__name",
                     "mission__lead__client__contact__name", "consultant__name", "consultant__trigramme")
    actions = None


class StaffingAdmin(ReturnToAppAdmin):
    list_display = ("mission", "consultant", "staffing_date", "charge", "comment")
    search_fields = ("mission__lead__name", "mission__description", "mission__deal_id", "mission__lead__client__organisation__company__name",
                     "mission__lead__client__contact__name", "consultant__name", "consultant__trigramme")
    date_hierarchy = "staffing_date"
    list_filter = ("mission__subsidiary", "mission__active")
    actions = None


admin.site.register(AnalyticCode, AnalyticCodeAdmin)
admin.site.register(MarketingProduct, MarketingProductAdmin)
admin.site.register(Mission, MissionAdmin)
admin.site.register(Holiday, HolidayAdmin)
admin.site.register(FinancialCondition, FinancialConditionAdmin)
admin.site.register(Timesheet)
admin.site.register(Staffing, StaffingAdmin)
