# coding:utf-8
"""
People form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
import bleach

from django.forms import models
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from django_select2.forms import ModelSelect2Widget, ModelSelect2MultipleWidget
from crispy_forms.layout import Layout, Column, Field, Row

from core.forms import PydiciSelect2WidgetMixin, TagChoices, PydiciCrispyForm
from people.models import Consultant, SalesMan
from core.models import Tag, TaggedItem


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

class ConsultantTagChoices(TagChoices):
    def __init__(self, *args, **kwargs):
        self.consultant = kwargs.pop("consultant", None)
        super(ConsultantTagChoices, self).__init__(*args, **kwargs)

    def get_queryset(self):
        qs = super(ConsultantTagChoices, self).get_queryset()
        if self.consultant:
            qs = qs.exclude(lead__id=self.consultant.id)  # Exclude existing tags
        return qs


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


class ConsultantTagForm(PydiciCrispyForm):
    """Add and create tags for a consultant"""
    def __init__(self, *args, **kwargs):
        consultant = kwargs.pop("consultant", None)
        super(ConsultantTagForm, self).__init__(*args, **kwargs)
        self.fields["tag"] = forms.ModelMultipleChoiceField(label=_("Tag"),
            widget=ConsultantTagChoices(consultant=consultant, attrs={"data-placeholder": _("New tags"), "style": "min-width: 200px;"}),
            queryset=Tag.objects)
        self.fields["level"] = forms.ChoiceField(label=_("Level"), choices=TaggedItem.TAG_LEVEL_TYPES, required=False)
        self.fields["nature"] = forms.ChoiceField(label=_("Nature"), choices=TaggedItem.TAG_NATURE_TYPES, required=False)
        self.helper.form_tag = False
        self.helper.layout = Layout(Row(
            Column(Field("tag"), css_class="col-lg-8"),
            Column(Field("level"), css_class="col-lg-2"),
            Column(Field("nature"), css_class="col-lg-2"),
            ),
        )


class ConsultantFilterTagForm(forms.Form):
    """Select only tag form, used for filtering consultants by tag"""
    def __init__(self, *args, **kwargs):
        super(ConsultantFilterTagForm, self).__init__(*args, **kwargs)
        self.fields["tag"] = forms.ModelMultipleChoiceField(widget=ConsultantTagChoices(attrs={"data-tags": "false", "style": "min-width: 200px;"}, required=False),
                                                            queryset=Tag.objects, label=False, required=False)
