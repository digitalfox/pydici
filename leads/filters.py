# coding:utf-8
"""
Leads filters
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from datetime import date

from django.utils.translation import gettext as _

import django_filters
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, Column, Field

from leads.models import Activity
from people.models import Consultant


class ActivityFilter(django_filters.FilterSet):
    responsible = django_filters.ChoiceFilter(method="responsible_filter",
        choices=(("ME", _("Me")), ("TEAM", _("My team")), ("TERRITORY", _("My business territory"))))
    state = django_filters.ChoiceFilter(method="state_filter",
        choices=(Activity.STATES + (("LATE", _("Late")),)))

    def responsible_filter(self, queryset, name, value):
        consultant = Consultant.objects.get(trigramme__iexact=self.request.user.username)
        if value == "ME":
            return queryset.filter(responsible=consultant)
        elif value == "TEAM":
            return queryset.filter(responsible__in=consultant.team(exclude_self=False))
        elif value == "TERRITORY":
            return queryset.filter(client_organisation__company__businessOwner=consultant)

        return queryset

    def state_filter(self, queryset, name, value):
        if value == "LATE":
            return queryset.filter(due_date__lt=date.today())
        else:
            return queryset.filter(state=value)


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
        Column(Submit('submit', _('Apply Filter'), css_class="filter-submit-btn"), css_class="col-md-2"),
        css_class="my-3"
    ))
