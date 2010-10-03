# coding:utf-8
"""
Core form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django.utils.translation import ugettext as _
from django import forms

class SearchForm(forms.Form):
    search = forms.CharField(max_length=100)
