# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib import admin

from expense.models import Expense, ExpenseCategory


class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("user", "description", "lead", "chargeable", "creation_date", "update_date")
    odering = ("creation_date")
    search_fields = ["description", "lead__name", "lead__client__organisation__company__name", "consultant__name"]
    list_filter = ["workflow_in_progress", "chargeable", "corporate_card", "user"]
    actions = None


class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    actions = None

admin.site.register(Expense, ExpenseAdmin)
admin.site.register(ExpenseCategory, ExpenseCategoryAdmin)
