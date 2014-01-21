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


class LeadsTable(tables.Table):
    client = tables.LinkColumn(verbose_name=_("Client"), viewname="crm.views.company_detail", args=[A("client.organisation.company.id")])
    name = tables.LinkColumn(verbose_name=_("Name"), viewname="leads.views.detail", args=[A("pk")])
    responsible = tables.LinkColumn(accessor="responsible", viewname="people.views.consultant_home", args=[A("responsible.id")])
    staffing_list = tables.Column()
    due_date = tables.TemplateColumn("""<span title="{{ record.due_date|date:"Ymd" }}">{{ record.due_date|default_if_none:"-" }}</span>""")  # Title attr is just used to have an easy to parse hidden value for sorting
    start_date = tables.TemplateColumn("""<span title="{{ record.start_date|date:"Ymd" }}">{{ record.start_date|default_if_none:"-" }}</span>""")  # Title attr is just used to have an easy to parse hidden value for sorting

    class Meta:
        model = Lead
        sequence = ("client", "name", "deal_id", "subsidiary", "responsible", "staffing_list", "sales", "state", "due_date", "start_date")
        fields = sequence
        attrs = {"class": "pydici-tables2"}


class ActiveLeadsTable(LeadsTable):
    class Meta:
        orderable = False  # Sort is done by jquery.datatable on client side
        attrs = {"class": "pydici-tables2", "id": "active_leads_table"}
        prefix = "active_leads_table"
        order_by = "creation_date"


class RecentArchivedLeadsTable(LeadsTable):
    class Meta:
        orderable = False  # Sort is done by jquery.datatable on client side
        attrs = {"class": "pydici-tables2", "id": "recent_archived_leads_table"}
        prefix = "recent_archived_leads_table"
