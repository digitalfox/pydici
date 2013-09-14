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


archive_mission_template = """{% load i18n %}{% if record.active %}
               <div id=mission_{{record.id}}></div><a href="javascript:;"
                  onClick="$.get('{% url 'staffing.views.deactivate_mission' record.id %}',
                                   process_mission_archive)">
                  <em>{% trans "Archive" %}</em></a>
           {% endif %}"""


class MissionTable(tables.Table):
    old_forecast = tables.BooleanColumn(accessor="no_staffing_update_since")
    no_forecast = tables.BooleanColumn(accessor="no_more_staffing_since")
    mission_id = tables.Column(accessor="mission_id", verbose_name=_("Mission id"))
    name = tables.LinkColumn(accessor="__unicode__", verbose_name=_("Name"), viewname="staffing.views.mission_home", args=[A("pk")])
    archive = tables.TemplateColumn(archive_mission_template, verbose_name=_("Archiving"))

    class Meta:
        model = Mission
        sequence = ("name", "nature", "mission_id", "probability", "price", "active", "old_forecast", "no_forecast", "archive")
        fields = sequence
