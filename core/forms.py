# coding:utf-8
"""
Core form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django import forms


class SearchForm(forms.Form):
    search = forms.CharField(max_length=100)
