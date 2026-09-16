# coding:utf-8
"""
Leads filters
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from django.utils.translation import gettext as _

from django_filters import FilterSet, ChoiceFilter, ModelMultipleChoiceFilter
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, Column, Field
from django_select2.forms import Select2MultipleWidget


from leads.models import Activity
from people.models import Consultant
from staffing.models import MarketingProduct


class ActivityFilter(FilterSet):
    responsible = ChoiceFilter(method="responsible_filter")
    state = ChoiceFilter(method="state_filter",
        choices=(Activity.STATES + (("LATE", _("Late")), ("SOON", _("Soon")))))
    marketing_products = ModelMultipleChoiceFilter(widget=Select2MultipleWidget, queryset=MarketingProduct.objects.all())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        responsibles = [[c["responsible__id"], c["responsible__name"]] for c in self.queryset.order_by("responsible__name").values("responsible__name", "responsible__id").distinct()]
        self.filters["responsible"].extra["choices"] = [("ME", _("Me")), ("TEAM", _("My team")), ("TERRITORY", _("My business territory"))] + [('', '---------')] + responsibles


    def responsible_filter(self, queryset, name, value):
        consultant = Consultant.objects.get(trigramme__iexact=self.request.user.username)
        if value == "ME":
            return queryset.filter(responsible=consultant)
        elif value == "TEAM":
            return queryset.filter(responsible__in=consultant.team(exclude_self=False, staffing=True))
        elif value == "TERRITORY":
            return queryset.filter(client_organisation__company__businessOwner=consultant)
        elif value.isdigit():
            return queryset.filter(responsible__id=value)
        else:
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
        fields = ["state", "objective", "nature", "responsible", "marketing_products"]


class ActivityFilterFormHelper(FormHelper):
    form_method = 'GET'
    layout = Layout(Row(
        Column(Field("state"), css_class="col-md-3 col-lg-1"),
        Column(Field("objective"), css_class="col-md-3 col-lg-2"),
        Column(Field("nature"), css_class="col-md-3 col-lg-2"),
        Column(Field("responsible"), css_class="col-md-3 col-lg-2"),
        Column(Field("marketing_products"), css_class="col-md-3 col-lg-3"),
        Column(Submit('submit', _('Apply Filter'), css_class="filter-submit-btn"), css_class="col-md-2"),
        css_class="my-3"
    ))
