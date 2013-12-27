# coding: utf-8
"""
Pydici staffing tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import ugettext as _

import django_tables2 as tables
from django_tables2.utils import A

from staffing.models import Mission


class InversedBooleanColumn(tables.BooleanColumn):
    """Boolean column that inverse True and False"""
    def render(self, value):
        return super(InversedBooleanColumn, self).render(not value)


class MissionTable(tables.Table):
    old_forecast = InversedBooleanColumn(accessor="no_staffing_update_since", verbose_name=_("Fcast updt"), attrs={"th": {"title": _("Up to date forecast")}}, orderable=False)
    no_forecast = InversedBooleanColumn(accessor="no_more_staffing_since", verbose_name=_("Fcast"), attrs={"th": {"title": _("Forecast in future")}}, orderable=False)
    mission_id = tables.Column(accessor="mission_id", verbose_name=_("Mission id"), orderable=False)
    name = tables.LinkColumn(accessor="__unicode__", verbose_name=_("Name"), viewname="staffing.views.mission_home", args=[A("pk")], orderable=False)
    archive = tables.TemplateColumn(template_name="staffing/_mission_table_archive_column.html", verbose_name=_("Archiving"), orderable=False)

    class Meta:
        model = Mission
        sequence = ("name", "subsidiary", "nature", "mission_id", "probability", "price", "active", "no_forecast", "old_forecast", "archive")
        fields = sequence
        attrs = {"class": "pydici-tables2"}
