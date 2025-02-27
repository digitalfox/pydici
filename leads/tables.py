# coding: utf-8
"""
Pydici leads tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.db.models import Q
from django.template.loader import get_template
from django.urls import reverse
from django.utils.html import escape

from django_datatables_view.base_datatable_view import BaseDatatableView
from taggit.models import Tag

from datetime import datetime, timedelta


from leads.models import Lead
from core.decorator import PydiciFeatureMixin, PydiciNonPublicdMixin
from crm.utils import get_subsidiary_from_session


class LeadsViewsReadMixin(PydiciNonPublicdMixin, PydiciFeatureMixin):
    """Internal access to leads data for CB views"""
    pydici_feature = {"leads_list_all", "leads"}


class LeadTableDT(LeadsViewsReadMixin, BaseDatatableView):
    """Leads tables backend for datatables"""
    columns = ["client", "name", "deal_id", "subsidiary", "responsible", "sales", "state", "creation_date"]
    order_columns = columns
    max_display_length = 500
    probaTemplate = get_template("leads/_state_column.html")
    consultantTemplate = get_template("people/__consultant_name.html")

    def _filter_on_subsidiary(self, qs):
        subsidiary = get_subsidiary_from_session(self.request)
        if subsidiary:
            qs = qs.filter(Q(subsidiary=subsidiary) | Q(staffing__company=subsidiary)).distinct()
        return qs

    def get_initial_queryset(self):
        qs  = Lead.objects.all()
        qs = self._filter_on_subsidiary(qs)
        return qs.select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")

    def render_column(self, row, column):
        if column == "responsible":
            if row.responsible:
                return self.consultantTemplate.render({"consultant": row.responsible})
            else:
                return "-"
        elif column == "client":
            return "<a href='{0}'>{1}</a>".format(row.client.get_absolute_url(), escape(row.client))
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
        search = self.request.GET.get('search[value]', None)
        qs = self._filter_on_subsidiary(qs)
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
    columns = ["client", "name", "deal_id", "subsidiary", "responsible", "staffing_list", "sales", "state", "proba", "creation_date", "due_date", "start_date", "update_date"]
    order_columns = columns
    dateTemplate = get_template("core/_date_column.html")
    pydici_feature = "leads"

    def get_initial_queryset(self):
        qs = Lead.objects.active()
        qs = self._filter_on_subsidiary(qs)
        return qs.select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")

    def render_column(self, row, column):
        if column in ("creation_date", "due_date", "start_date", "update_date"):
            return self.dateTemplate.render({"date": getattr(row, column)})
        else:
            return super(ActiveLeadTableDT, self).render_column(row, column)


class RecentArchivedLeadTableDT(ActiveLeadTableDT):
    columns = ["client", "name", "deal_id", "subsidiary", "responsible", "staffing_list", "sales", "state", "proba",
               "creation_date", "start_date", "update_date"]
    order_columns = columns
    def get_initial_queryset(self):
        today = datetime.today()
        delay = timedelta(days=40)
        qs = Lead.objects.passive().filter(Q(update_date__gte=(today - delay)) |
                                                            Q(state="SLEEPING"))
        qs = self._filter_on_subsidiary(qs)
        qs = qs.select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")
        return qs


class TagTableDT(PydiciNonPublicdMixin, PydiciFeatureMixin, BaseDatatableView):
    """Tag tables backend for datatables"""
    pydici_feature = {"leads_list_all", "leads"}
    columns = ["select", "name"]
    order_columns = columns

    def render_column(self, row, column):
        if column == "name":
            return "<a href='{0}'>{1}</a>".format(reverse("leads:tag", args=[row.id,]), row.name)
        elif column == "select":
            return "<input id='tag-%s' type='checkbox'onclick='gather_tags_to_merge()' />" % row.id

    def get_initial_queryset(self):
        return Tag.objects.all()

    def filter_queryset(self, qs):
        search = self.request.GET.get(u'search[value]', None)
        filters = None
        for word in search.split():
            filter = Q(name__icontains=word)
            if not filters:
                filters = filter
            else:
                filters |= filter
        if filters:
            qs = qs.filter(filters)
        return qs


class ClientCompanyLeadTableDT(LeadTableDT):
    def get_initial_queryset(self):
        return Lead.objects.filter(client__organisation__company__id=self.kwargs["clientcompany_id"]).select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")


class LeadToBill(LeadTableDT):
        """Track missing bills"""
        columns = ("client", "name", "deal_id", "subsidiary", "responsible", "creation_date", "sales", "to_be_billed")
        order_columns = columns
        max_display_length = 100

        def get_initial_queryset(self):
            return Lead.objects.filter(state="WON", mission__active=True).distinct()

        def render_column(self, row, column):
            if column == "to_be_billed":
                return round(row.still_to_be_billed()/1000, 3)
            else:
                return super(LeadToBill, self).render_column(row, column)


class SupplierLeadTableDT(LeadTableDT):
    def get_initial_queryset(self):
        qs = Lead.objects.filter(mission__timesheet__consultant__subcontractor_company__company_id=self.kwargs["supplier_id"]).distinct()
        return qs.select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")


class BusinessBrokerLeadTableDT(LeadTableDT):
    """Business broker or paying authority leads"""
    def get_initial_queryset(self):
        qs = Lead.objects.filter(Q(business_broker__company_id=self.kwargs["businessbroker_id"]) | Q(paying_authority__company_id=self.kwargs["businessbroker_id"]))
        qs = qs.distinct()
        return qs.select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")


