# coding:utf-8
"""
Leads filters
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from django.utils.translation import gettext as _

import django_filters
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, Column, Field

from leads.models import Activity
from people.models import Consultant


class ActivityFilter(django_filters.FilterSet):
    responsible = django_filters.ChoiceFilter(method="responsible_filter",
        choices=(("ME", _("Me")), ("TEAM", _("My team"))), empty_label=_("Everybody"))

    def responsible_filter(self, queryset, name, value):
        consultant = Consultant.objects.get(trigramme__iexact=self.request.user.username)
        if value == "ME":
            return queryset.filter(responsible=consultant)
        if value == "TEAM":
            return queryset.filter(responsible__in=consultant.team(exclude_self=False))
        return queryset


    class Meta:
        model = Activity
        fields = ["state", "objective", "nature", "responsible"]


class ActivityFilterFormHelper(FormHelper):
    form_method = 'GET'
    layout = Layout(Row(
        Column(Field("state"), css_class="col-md-2"),
        Column(Field("objective"), css_class="col-md-2"),
        Column(Field("nature"), css_class="col-md-2"),
        Column(Field("responsible"), css_class="col-md-2"),
        Column(Submit('submit', 'Apply Filter', css_class="filter-submit-btn"), css_class="col-md-2"),
        css_class="my-3"
    ))
