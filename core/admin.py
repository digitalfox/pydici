# coding:utf-8
"""
Django administration setup for pydici core module
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext

from pydici.core.models import Subsidiary

class SubsidiaryAdmin(admin.ModelAdmin):
    ordering = ("name",)
    actions = None


admin.site.register(Subsidiary, SubsidiaryAdmin)
