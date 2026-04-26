# coding:utf-8
"""
Leads filters
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from datetime import date, timedelta

from django.utils.translation import gettext as _
from django.db.models import Q

from django_filters import FilterSet, ChoiceFilter
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, Column, Field

from leads.models import Activity
from people.models import Consultant


class ActivityFilter(FilterSet):
    responsible = ChoiceFilter(method="responsible_filter",
        choices=(("ME", _("Me")), ("TEAM", _("My team")), ("TERRITORY", _("My business territory"))))
    state = ChoiceFilter(method="state_filter",
        choices=(Activity.STATES + (("LATE", _("Late")), ("SOON", _("Soon")))))

    def responsible_filter(self, queryset, name, value):
        consultant = Consultant.objects.get(trigramme__iexact=self.request.user.username)
        if value == "ME":
            return queryset.filter(responsible=consultant)
        elif value == "TEAM":
            return queryset.filter(responsible__in=consultant.team(exclude_self=False, staffing=True))
        elif value == "TERRITORY":
            return queryset.filter(client_organisation__company__businessOwner=consultant)

        return queryset

    def state_filter(self, queryset, name, value):
        if value == "LATE":
            return queryset.late()
        elif value == "SOON":
            return queryset.soon()
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
