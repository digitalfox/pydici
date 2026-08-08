"""
Staffing filters
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from django.utils.translation import gettext as _

from django_filters import FilterSet
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, Column, Field


from .models import Mission

class MissionFilter(FilterSet):

    class Meta:
        model = Mission
        fields = ["responsible", "nature", "billing_mode", "management_mode", "marketing_product"]

class MissionFilterFormHelper(FormHelper):
    form_method = 'GET'
    layout = Layout(Row(
        Column(Field("responsible"), css_class="col-md-2 col-xs-12"),
        Column(Field("nature"), css_class="col-md-2 col-xs-12"),
        Column(Field("billing_mode"), css_class="col-md-2 col-xs-12"),
        Column(Field("management_mode"), css_class="col-md-2 col-xs-12"),
        Column(Field("marketing_product"), css_class="col-md-2 col-xs-12"),
        Column(Submit('submit', _('Apply Filter'), css_class="filter-submit-btn"), css_class="col-md-2 col-xs-12"),
        css_class="my-3"
    ))
