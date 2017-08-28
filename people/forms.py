# coding:utf-8
"""
People form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django import forms
from django.forms import ModelChoiceField
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError

from django_select2.forms import ModelSelect2Widget, ModelSelect2MultipleWidget
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div, Column, Field


from people.models import Consultant, SalesMan
from core.forms import PydiciCrispyForm


class ConsultantChoices(ModelSelect2Widget):
    model = Consultant
    search_fields = ['name__icontains', 'trigramme__icontains']

    def get_queryset(self):
        return Consultant.objects.filter(active=True)


class ConsultantMChoices(ModelSelect2MultipleWidget):
    model = Consultant
    search_fields = ConsultantChoices.search_fields

    def get_queryset(self):
        return Consultant.objects.filter(active=True)


class SalesManChoices(ModelSelect2Widget):
    model = SalesMan
    search_fields = ['name__icontains', 'trigramme__icontains']

    def get_queryset(self):
        return SalesMan.objects.filter(active=True)


class ConsultantForm(forms.models.ModelForm):
    class Meta:
        model = Consultant
        fields = "__all__"

    def clean_subcontractor_company(self):
        """Ensure subcontractor flag is on if subcontractor company is defined"""
        if self.cleaned_data["subcontractor_company"] and not self.cleaned_data["subcontractor"]:
            raise ValidationError(_("Subcontractor company can only be defined for subcontractors"))
        else:
            return self.cleaned_data["subcontractor_company"]

class SimilarConsultantForm(PydiciCrispyForm):
    consultant = ModelChoiceField(widget = ConsultantChoices(attrs={'data-placeholder':_("Select a similar consultant...")}), queryset=Consultant.objects)

    def __init__(self, *args, **kwargs):
        super(SimilarConsultantForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column("consultant", css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)
