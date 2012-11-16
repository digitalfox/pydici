# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib import admin
from django.utils.translation import ugettext

from pydici.actionset.models import ActionSet, Action, ActionState


class ActionInlineAdmin(admin.TabularInline):
    model = Action


class ActionSetAdmin(admin.ModelAdmin):
    list_display = ("name", "trigger", "active")
    search_fields = ["name", "trigger"]
    list_filter = ["active", ]
    actions = None
    inlines = [ActionInlineAdmin, ]


class ActionAdmin(admin.ModelAdmin):
    list_display = ("name", "actionset")
    search_fields = ["name", "actionset__name"]
    actions = None


class ActionStateAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "target", "state", "creation_date", "update_date")
    fieldsets = [(ugettext("Action state"), {"fields": ["action", "user", "state" ]}),
                 (ugettext("Target object"), {"fields": ["target_type", "target_id"]})]
    search_fields = ["action__actionset__name", "action__name", "user"]
    actions = None
    list_filter = ["state", "user"]
    date_hierarchy = "update_date"

admin.site.register(ActionSet, ActionSetAdmin)
admin.site.register(Action, ActionAdmin)
admin.site.register(ActionState, ActionStateAdmin)
