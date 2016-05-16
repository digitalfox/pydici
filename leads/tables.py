# coding: utf-8
"""
Pydici leads tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import ugettext as _
from django.db.models import Q

import django_tables2 as tables
from django_tables2.utils import A
from django_datatables_view.base_datatable_view import BaseDatatableView

from leads.models import Lead
from core.utils import TABLES2_HIDE_COL_MD

class BaseLeadsTable(tables.Table):
    client = tables.LinkColumn(verbose_name=_("Client"), viewname="crm.views.company_detail",
                               args=[A("client.organisation.company.id")])
    name = tables.LinkColumn(verbose_name=_("Name"), viewname="leads.views.detail", args=[A("pk")])
    responsible = tables.LinkColumn(accessor="responsible", viewname="people.views.consultant_home",
                                    args=[A("responsible.id")])
    creation_date = tables.TemplateColumn("""<span title="{{ record.creation_date|date:"YmdHis" }}">{{ record.creation_date|date:"j F" }}</span>""",
                                          attrs=TABLES2_HIDE_COL_MD)  # Title span is just used to have an easy to parse hidden value for sorting


    class Meta:
        model = Lead
        sequence = ("client", "name", "deal_id", "subsidiary", "responsible", "sales", "state", "creation_date")
        fields = sequence


class LeadsTable(BaseLeadsTable):
    staffing_list = tables.Column(attrs=TABLES2_HIDE_COL_MD)
    due_date = tables.TemplateColumn("""<span title="{{ record.due_date|date:"Ymd" }}">{{ record.due_date|date:"j F"|default_if_none:"-" }}</span>""", attrs=TABLES2_HIDE_COL_MD)  # Title span is just used to have an easy to parse hidden value for sorting
    start_date = tables.TemplateColumn("""<span title="{{ record.start_date|date:"Ymd" }}">{{ record.start_date|date:"j F"|default_if_none:"-" }}</span>""", attrs=TABLES2_HIDE_COL_MD)  # Title span is just used to have an easy to parse hidden value for sorting
    proba = tables.TemplateColumn("""{% with record.getStateProba as proba %}{% if proba %}
                                            <div class='proba' data-toggle='tooltip' data-content='<table style="margin-bottom:0" class="table table-striped table-condensed">{% for code, state, score in proba %}<tr><td>{{state }}</td><td>{{ score }} %</td></tr>{% endfor %}</table>'>
                                                <div
                                                    {% ifequal proba.0.0 "WON" %}style="color:green" class="glyphicon glyphicon-ok-circle"{% endifequal %}
                                                    {% ifequal proba.0.0 "LOST" %}style="color:red" class="glyphicon glyphicon-remove-circle"{% endifequal %}
                                                    {% ifequal proba.0.0 "FORGIVEN" %}style="color:orange" class="glyphicon glyphicon-ban-circle"{% endifequal %}
                                                    >
                                                </div><small> {{proba.0.2}}&nbsp;%</small>
                                            </div>
                                     {% endif %}{% endwith %}""", attrs=TABLES2_HIDE_COL_MD)


    class Meta:
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

class AllLeadsTable(BaseLeadsTable):
    class Meta:
        attrs = {"class": "pydici-tables2 table table-hover table-striped table-condensed", "id": "all_leads_table"}



class LeadTableDT(BaseDatatableView):
    """Leads tables backend for datatables"""
    columns = ["client", "name", "deal_id", "subsidiary", "responsible", "sales", "state", "creation_date"]
    order_columns = columns
    max_display_length = 500

    def get_initial_queryset(self):
        return Lead.objects.all().select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")

    def render_column(self, row, column):
        if column == "responsible":
            if row.responsible:
                return u"<a href='{0}'>{1}</a>".format(row.responsible.get_absolute_url(), row.responsible.name)
            else:
                return u"-"
        elif column == "client":
            return u"<a href='{0}'>{1}</a>".format(row.client.get_absolute_url(), row.client)
        elif column == "sales":
            if row.sales:
                return round(float(row.sales),3)
            else:
                return ""
        elif column == "creation_date":
            return row.creation_date.strftime("%d/%m/%y")
        else:
            return super(LeadTableDT, self).render_column(row, column)

    def filter_queryset(self, qs):
        """ simple search on some attributes"""
        search = self.request.GET.get(u'search[value]', None)
        if search:
            qs = qs.filter(Q(name__icontains=search) |
                           Q(description__icontains=search) |
                           Q(tags__name__iexact=search) |
                           Q(client__contact__name__icontains=search) |
                           Q(client__organisation__company__name__icontains=search) |
                           Q(client__organisation__name__iexact=search) |
                           Q(deal_id__icontains=search))
        return qs