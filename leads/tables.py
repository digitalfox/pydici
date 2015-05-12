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
from core.utils import TABLES2_HIDE_COL_MD


class LeadsTable(tables.Table):
    client = tables.LinkColumn(verbose_name=_("Client"), viewname="crm.views.company_detail", args=[A("client.organisation.company.id")])
    name = tables.LinkColumn(verbose_name=_("Name"), viewname="leads.views.detail", args=[A("pk")])
    responsible = tables.LinkColumn(accessor="responsible", viewname="people.views.consultant_home", args=[A("responsible.id")])
    staffing_list = tables.Column(attrs=TABLES2_HIDE_COL_MD)
    due_date = tables.TemplateColumn("""<span title="{{ record.due_date|date:"Ymd" }}">{{ record.due_date|date:"j F"|default_if_none:"-" }}</span>""", attrs=TABLES2_HIDE_COL_MD)  # Title span is just used to have an easy to parse hidden value for sorting
    start_date = tables.TemplateColumn("""<span title="{{ record.start_date|date:"Ymd" }}">{{ record.start_date|date:"j F"|default_if_none:"-" }}</span>""", attrs=TABLES2_HIDE_COL_MD)  # Title span is just used to have an easy to parse hidden value for sorting
    creation_date = tables.TemplateColumn("""<span title="{{ record.creation_date|date:"YmdHis" }}">{{ record.creation_date|date:"j F" }}</span>""", attrs=TABLES2_HIDE_COL_MD)  # Title span is just used to have an easy to parse hidden value for sorting
    proba = tables.TemplateColumn("""{% if record.getStateProba %}
                                            <div class='proba' data-toggle='tooltip' data-content='<table style="margin-bottom:0" class="table table-striped table-condensed">{% for code, state, proba in record.getStateProba %}<tr><td>{{state }}</td><td>{{ proba }} %</td></tr>{% endfor %}</table>'>
                                                <div
                                                    {% ifequal record.getStateProba.0.0 "WON" %}style="color:green" class="glyphicon glyphicon-ok-circle"{% endifequal %}
                                                    {% ifequal record.getStateProba.0.0 "LOST" %}style="color:red" class="glyphicon glyphicon-remove-circle"{% endifequal %}
                                                    {% ifequal record.getStateProba.0.0 "FORGIVEN" %}style="color:orange" class="glyphicon glyphicon-ban-circle"{% endifequal %}
                                                    {% ifequal record.getStateProba.0.0 "SLEEPING" %}style="color:"yellow" class="glyphicon glyphicon-cloud"{% endifequal %}
                                                    >
                                                </div><small> {{record.getStateProba.0.2}}&nbsp;%</small>
                                            </div>
                                     {% endif %}""", attrs=TABLES2_HIDE_COL_MD)


    class Meta:
        model = Lead
        sequence = ("client", "name", "deal_id", "subsidiary", "responsible", "staffing_list", "sales", "state", "proba", "creation_date", "due_date", "start_date")
        fields = sequence
        attrs = {"class": "pydici-tables2 table table-hover table-striped table-condensed"}


class ActiveLeadsTable(LeadsTable):
    class Meta:
        orderable = False  # Sort is done by jquery.datatable on client side
        attrs = {"class": "pydici-tables2 table table-hover table-striped table-condensed", "id": "active_leads_table"}
        prefix = "active_leads_table"
        order_by = "creation_date"


class RecentArchivedLeadsTable(LeadsTable):
    class Meta:
        orderable = False  # Sort is done by jquery.datatable on client side
        attrs = {"class": "pydici-tables2 table table-hover table-striped table-condensed", "id": "recent_archived_leads_table"}
        prefix = "recent_archived_leads_table"
