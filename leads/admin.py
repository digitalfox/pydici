# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from leads.models import Lead

from leads.forms import LeadForm
from leads.utils import post_save_lead
from core.admin import ReturnToAppAdmin


class LeadAdmin(ReturnToAppAdmin):
    list_display = ("name", "client", "subsidiary", "responsible", "state", "due_date", "update_date_strf")
    fieldsets = [
        (None, {"fields": ["name", "client", "subsidiary", "description", "action"]}),
        (_("State and tracking"), {"fields": ["responsible", "state", "due_date", "start_date", "deal_id", "client_deal_id"]}),
        (_("Commercial"), {"fields": ["sales", "business_broker", "paying_authority", "salesman", ]}),
        (_("Staffing"), {"fields": ["staffing", "external_staffing"]}),
        (None, {"fields": ["send_email", ]})
        ]
    ordering = ("creation_date",)
    actions = None
    filter_horizontal = ["staffing"]
    list_filter = ["state", "subsidiary"]
    date_hierarchy = "update_date"
    search_fields = ["name", "description", "action",
                     "responsible__name", "responsible__trigramme",
                     "salesman__name", "salesman__trigramme",
                     "client__contact__name", "client__organisation__company__name",
                     "client__organisation__name",
                     "staffing__trigramme", "staffing__name",
                     "deal_id", "client_deal_id"]

    def save_model(self, request, obj, form, change):
        form.save_m2m()  # Save many to many relations
        post_save_lead(request, obj)


admin.site.register(Lead, LeadAdmin)
