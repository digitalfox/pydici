# coding:utf-8
"""
People form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.forms import models
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError

from django_select2 import AutoModelSelect2Field, AutoModelSelect2MultipleField

from people.models import Consultant, SalesMan
from core.forms import PydiciSelect2Field


class ConsultantChoices(PydiciSelect2Field, AutoModelSelect2Field):
    queryset = Consultant.objects
    search_fields = ['name__icontains', 'trigramme__icontains']

    def get_queryset(self):
        return Consultant.objects.filter(active=True)


class ConsultantMChoices(PydiciSelect2Field, AutoModelSelect2MultipleField):
    queryset = Consultant.objects
    search_fields = ConsultantChoices.search_fields

    def get_queryset(self):
        return Consultant.objects.filter(active=True)


class SalesManChoices(PydiciSelect2Field, AutoModelSelect2Field):
    queryset = SalesMan.objects.filter(active=True)
    search_fields = ['name__icontains', 'trigramme__icontains']


class ConsultantForm(models.ModelForm):
    class Meta:
        model = Consultant

    def clean_subcontractor_company(self):
        """Ensure subcontractor flag is on if subcontractor company is defined"""
        if self.cleaned_data["subcontractor_company"] and not self.cleaned_data["subcontractor"]:
            raise ValidationError(_("Subcontractor company can only be defined for subcontractors"))
        else:
            return self.cleaned_data["subcontractor_company"]
