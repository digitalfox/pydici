# coding:utf-8
"""
People form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.forms import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from django_select2.forms import ModelSelect2Widget, ModelSelect2MultipleWidget

from core.forms import PydiciSelect2WidgetMixin
from people.models import Consultant, SalesMan


class ConsultantChoices(PydiciSelect2WidgetMixin, ModelSelect2Widget):
    model = Consultant
    search_fields = ['name__icontains', 'trigramme__icontains']

    def get_queryset(self):
        return Consultant.objects.filter(active=True)


class ConsultantMChoices(PydiciSelect2WidgetMixin, ModelSelect2MultipleWidget):
    model = Consultant
    search_fields = ConsultantChoices.search_fields

    def get_queryset(self):
        return Consultant.objects.filter(active=True)


class SalesManChoices(PydiciSelect2WidgetMixin, ModelSelect2Widget):
    model = SalesMan
    search_fields = ['name__icontains', 'trigramme__icontains']

    def get_queryset(self):
        return SalesMan.objects.filter(active=True)


class ConsultantForm(models.ModelForm):
    class Meta:
        model = Consultant
        fields = "__all__"

    def clean_subcontractor_company(self):
        """Ensure subcontractor flag is on if subcontractor company is defined"""
        if self.cleaned_data["subcontractor_company"] and not self.cleaned_data["subcontractor"]:
            raise ValidationError(_("Subcontractor company can only be defined for subcontractors"))
        else:
            return self.cleaned_data["subcontractor_company"]
