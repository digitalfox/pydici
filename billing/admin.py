# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext

from ajax_select import make_ajax_form
from ajax_select.admin import AjaxSelectAdmin

from pydici.billing.models import Bill
from pydici.billing.forms import BillForm


#class BillAdmin(AjaxSelectAdmin):
class BillAdmin(AjaxSelectAdmin):
    list_display = ("id", "bill_id", "lead", "state", "amount", "creation_date", "due_date", "payment_date", "comment")
    ordering = ("creation_date",)
    actions = None
    list_filter = ["state", "creation_date", "due_date", "payment_date", "previous_year_bill"]
    search_fields = ["lead__name", "lead__client__organisation__name", "comment",
                     "lead_paying_authority__name", "lead_paying_authority__company",
                     "lead__client__contact__name", "lead__client__organisation__company__name"]
    form = BillForm

admin.site.register(Bill, BillAdmin)
