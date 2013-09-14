# coding: utf-8
"""
Pydici leads tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import ugettext as _

import django_tables2 as tables
from django_tables2.utils import A

from leads.models import Lead


class LeadTable(tables.Table):
    name = tables.LinkColumn(accessor="__unicode__", verbose_name=_("Name"), viewname="leads.views.detail", args=[A("pk")])
    responsible = tables.LinkColumn(accessor="responsible", viewname="people.views.consultant_home", args=[A("responsible.id")])
    staffing_list = tables.Column(orderable=False)

    class Meta:
        model = Lead
        sequence = ("name", "deal_id", "subsidiary", "responsible", "staffing_list", "sales", "state", "due_date", "start_date")
        fields = sequence
