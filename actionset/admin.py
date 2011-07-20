# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django.contrib import admin

from pydici.actionset.models import ActionSet, Action, ActionState

class ActionInlineAdmin(admin.TabularInline):
    model = Action

class ActionSetAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ["name", ]
    actions = None
    inlines = [ActionInlineAdmin, ]

class ActionAdmin(admin.ModelAdmin):
    list_display = ("name", "actionset")
    search_fields = ["name", "actionset__name"]
    actions = None

class ActionStateAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "done", "creation_date", "update_date")
    fieldsets = [(None, {"fields" : ["done", ] }), ]
    search_fields = ["action__actionset__name", "action__name", "user"]
    actions = None
    list_filter = ["done", "user"]
    date_hierarchy = "update_date"

admin.site.register(ActionSet, ActionSetAdmin)
admin.site.register(Action, ActionAdmin)
admin.site.register(ActionState, ActionStateAdmin)
