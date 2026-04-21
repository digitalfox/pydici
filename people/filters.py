# coding:utf-8
"""
People filters
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from django.utils.translation import gettext as _
from django.db.models import F

from django_filters import FilterSet, ModelChoiceFilter, ChoiceFilter
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, Column, Field

from people.models import Consultant, ConsultantProfile
from crm.utils import get_subsidiary_from_session

def manager_filter_choices(request):
    managers = Consultant.objects.filter(active=True, subcontractor=False, staffing_manager_id=F("id"))
    subsidiary = get_subsidiary_from_session(request)
    if subsidiary:
        managers = managers.filter(company=subsidiary)
    return managers

class ConsultantFilter(FilterSet):
    team = ModelChoiceFilter(method="team_filter", label=_("Team"), queryset=manager_filter_choices)
    profil = ModelChoiceFilter(queryset=ConsultantProfile.objects.filter(consultant__active=True, consultant__productive=True).distinct())
    subcontractor = ChoiceFilter(label=_("Subcontracting"), choices=[(True, _("Yes")), (False, _("No"))], empty_label=_("Anyone"))

    @property
    def qs(self):
        queryset = super().qs
        subsidiary = get_subsidiary_from_session(self.request)
        if subsidiary:
            queryset = queryset.filter(company=subsidiary)
        return queryset

    def team_filter(self, queryset, name, value):
        if value:
            queryset = queryset.filter(staffing_manager=value)
        return queryset

    class Meta:
        model = Consultant
        fields = ["subcontractor", "profil"]


class ConsultantFilterFormHelper(FormHelper):
    form_method = 'GET'
    layout = Layout(Row(
        Column(Field("profil"), css_class="col-md-2"),
        Column(Field("team"), css_class="col-md-2"),
        Column(Field("subcontractor"), css_class="col-md-2"),
        Column(Submit('submit', _('Apply Filter'), css_class="filter-submit-btn"), css_class="col-md-2"),
        css_class="my-3"
    ))
