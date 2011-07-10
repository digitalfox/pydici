# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django.contrib import admin

from pydici.expense.models import Expense

class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("consultant", "description", "lead", "chargeable", "creation_date", "update_date")
    odering = ("creation_date")
    search_fields = ["description", "lead__name", "lead__client__organisation__company__name", "consultant__name"]
    actions = None

admin.site.register(Expense, ExpenseAdmin)
