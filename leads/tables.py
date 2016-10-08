# coding: utf-8
"""
Pydici leads tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import ugettext as _
from django.db.models import Q
from django.template.loader import get_template

from django_datatables_view.base_datatable_view import BaseDatatableView

from datetime import datetime, timedelta

from leads.models import Lead
from core.decorator import PydiciFeatureMixin, PydiciNonPublicdMixin


class LeadsViewsReadMixin(PydiciNonPublicdMixin, PydiciFeatureMixin):
    """Internal access to leads data for CB views"""
    pydici_feature = set(["leads_list_all", "leads"])


class LeadTableDT(LeadsViewsReadMixin, BaseDatatableView):
    """Leads tables backend for datatables"""
    columns = ["client", "name", "deal_id", "subsidiary", "responsible", "sales", "state", "creation_date"]
    order_columns = columns
    max_display_length = 500
    probaTemplate = get_template("leads/_state_column.html")

    def get_initial_queryset(self):
        return Lead.objects.all().select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")

    def render_column(self, row, column):
        if column == "responsible":
            if row.responsible:
                data = u"<a href='{0}'>{1}</a>".format(row.responsible.get_absolute_url(), row.responsible.name)
                if row.responsible.is_in_holidays():
                    data += """ <span class="glyphicon glyphicon-sunglasses" title="{0}"></span>""".format(_('on holidays !'))
                return data
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
        elif column == "staffing_list":
            return row.staffing_list()
        elif column == "proba":
            return self.probaTemplate.render({"proba": row.getStateProba()})
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
                           Q(responsible__name__icontains=search) |
                           Q(subsidiary__name__icontains=search) |
                           Q(deal_id__icontains=search))
            qs = qs.distinct()
        return qs


class ActiveLeadTableDT(LeadTableDT):
    columns = ["client", "name", "deal_id", "subsidiary", "responsible", "staffing_list", "sales", "state", "proba", "creation_date", "due_date", "start_date"]
    order_columns = columns
    dateTemplate = get_template("leads/_date_column.html")
    pydici_feature = "leads"

    def get_initial_queryset(self):
        return Lead.objects.active().select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")

    def render_column(self, row, column):
        if column in ("creation_date", "due_date", "start_date"):
            return self.dateTemplate.render({"date": getattr(row, column)})
        else:
            return super(ActiveLeadTableDT, self).render_column(row, column)


class RecentArchivedLeadTableDT(ActiveLeadTableDT):
    def get_initial_queryset(self):
        today = datetime.today()
        delay = timedelta(days=40)
        qs = Lead.objects.passive().filter(Q(update_date__gte=(today - delay)) |
                                                            Q(state="SLEEPING"))
        qs = qs.order_by("state", "-update_date").select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")
        return qs

