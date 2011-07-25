# coding:utf-8
"""
Django administration setup for pydici core module
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib import admin

from pydici.core.models import Subsidiary

class SubsidiaryAdmin(admin.ModelAdmin):
    ordering = ("name",)
    actions = None


admin.site.register(Subsidiary, SubsidiaryAdmin)
