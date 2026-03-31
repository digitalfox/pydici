# coding: utf-8
"""
Pydici leads tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from leads.views import activity
from django.db.models import Q
from django.template.loader import get_template
from django.utils.html import escape
from django.urls import reverse

from django_datatables_view.base_datatable_view import BaseDatatableView

from datetime import datetime, timedelta


from leads.models import Lead, Activity
from core.decorator import PydiciFeatureMixin, PydiciNonPublicdMixin
from crm.utils import get_subsidiary_from_session
from leads.filters import ActivityFilter


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
    nameTemplate = get_template("leads/__lead_name.html")

    def _filter_on_subsidiary(self, qs):
        subsidiary = get_subsidiary_from_session(self.request)
        if subsidiary:
            qs = qs.filter(Q(subsidiary=subsidiary) | Q(staffing__company=subsidiary)).distinct()
        return qs

    def get_initial_queryset(self):
        qs = Lead.objects.all()
        qs = self._filter_on_subsidiary(qs)
        return qs.select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")

    def render_column(self, row, column):
        if column == "responsible":
            if row.responsible:
                return self.consultantTemplate.render({"consultant": row.responsible})
            else:
                return "-"
        elif column == "name":
            return self.nameTemplate.render({"lead": row})
        elif column == "client":
            return "<a href='{0}'>{1}</a>".format(row.client.get_absolute_url(), escape(row.client))
        elif column == "sales":
            if row.sales:
                return round(float(row.sales), 3)
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
        if search:
            qs = qs.filter(Q(name__icontains=search) |
                           Q(description__icontains=search) |
                           Q(tags__name__iexact=search) |
                           Q(client__contact__name__icontains=search) |
                           Q(client__organisation__company__name__icontains=search) |
                           Q(client__organisation__name__iexact=search) |
                           Q(responsible__name__icontains=search) |
                           Q(subsidiary__name__icontains=search) |
                           Q(client_deal_id__icontains=search) |
                           Q(deal_id__icontains=search))
            qs = qs.distinct()
        return qs


class ActiveLeadTableDT(LeadTableDT):
    columns = ["client", "name", "deal_id", "subsidiary", "responsible", "staffing_list", "sales", "state", "proba", "creation_date", "due_date", "start_date", "update_date"]
    order_columns = columns
    date_template = get_template("core/_date_column.html")
    pydici_feature = "leads"

    def get_initial_queryset(self):
        qs = Lead.objects.active()
        qs = self._filter_on_subsidiary(qs)
        return qs.select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")

    def render_column(self, row, column):
        if column in ("creation_date", "due_date", "start_date", "update_date"):
            late = column == "due_date" and row.is_late()
            return self.date_template.render({"date": getattr(row, column), "late": late})
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


class ClientCompanyLeadTableDT(LeadTableDT):
    def get_initial_queryset(self):
        qs = Lead.objects.filter(client__organisation__company__id=self.kwargs["clientcompany_id"])
        qs = self._filter_on_subsidiary(qs)
        qs = qs.select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")
        return qs


class LeadToBill(LeadTableDT):
    """Track missing bills"""
    columns = ("client", "name", "deal_id", "subsidiary", "responsible", "creation_date", "sales", "to_be_billed")
    order_columns = columns
    max_display_length = 100

    def get_initial_queryset(self):
        qs = Lead.objects.filter(state="WON", mission__active=True)
        qs = self._filter_on_subsidiary(qs)
        qs = qs.select_related("client__contact", "client__organisation__company", "responsible", "subsidiary")
        return qs.distinct()

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


class ActivityTableDT(PydiciNonPublicdMixin, PydiciFeatureMixin, BaseDatatableView):
    pydici_feature = {"leads"}
    columns = ["name", "responsible", "state", "nature", "objective", "client_organisation", "contact", "creation_date", "due_date"]
    order_columns = columns
    max_display_length = 500
    date_template = get_template("core/_date_column.html")
    consultantTemplate = get_template("people/__consultant_name.html")

    def _filter_on_subsidiary(self, qs):
        subsidiary = get_subsidiary_from_session(self.request)
        if subsidiary:
            qs = qs.filter(subsidiary=subsidiary)
        return qs

    def get_initial_queryset(self):
        filter = ActivityFilter(self.request.GET, queryset=Activity.objects.all(), request=self.request)
        qs = filter.qs
        qs = self._filter_on_subsidiary(qs)
        return qs.select_related("contact", "client_organisation__company", "responsible", "subsidiary")

    def filter_queryset(self, qs):
        """ simple search on some attributes"""
        search = self.request.GET.get('search[value]', None)
        if search:
            qs = qs.filter(Q(name__icontains=search) |
                        Q(activitycomment__comment__icontains=search) |
                        Q(contact__name__icontains=search) |
                        Q(client_organisation__company__name__icontains=search) |
                        Q(client_organisation__name__icontains=search) |
                        Q(business_broker__contact__name__icontains=search) |
                        Q(business_broker__company__name__icontains=search) |
                        Q(responsible__name__icontains=search) |
                        Q(subsidiary__name__icontains=search))

        return qs

    def render_column(self, row, column):
        if column == "name":
            return "<a href='%s'>%s</a>" % (reverse("leads:activity_detail", args=[row.id]), row.name)
        elif column == "responsible":
            if row.responsible:
                return self.consultantTemplate.render({"consultant": row.responsible})
            else:
                return "-"
        elif column == "client_organisation":
            if row.client_organisation:
                return "<a href='{0}'>{1}</a>".format(row.client_organisation.get_absolute_url(), escape(row.client_organisation))
            else:
                return "-"
        elif column == "contact":
            if row.contact:
                return "<a href='{0}'>{1}</a>".format(row.contact.get_absolute_url(), escape(row.contact))
            else:
                return "-"
        elif column in ("creation_date", "expense_date", "due_date"):
            late = column == "due_date" and row.is_late()
            return self.date_template.render({"date": getattr(row, column), "late": late})
        else:
            return super(ActivityTableDT, self).render_column(row, column)


class ContactActivityTableDT(ActivityTableDT):
    def get_initial_queryset(self):
        qs = Activity.objects.filter(contact__id=self.kwargs["contact_id"])
        qs = self._filter_on_subsidiary(qs)
        return qs.select_related("contact", "client_organisation__company", "responsible", "subsidiary")


class CompanyActivityTableDT(ActivityTableDT):
    def get_initial_queryset(self):
        qs = Activity.objects.filter(client_organisation__company__id=self.kwargs["company_id"])
        qs = self._filter_on_subsidiary(qs)
        return qs.select_related("contact", "client_organisation__company", "responsible", "subsidiary")


class RelatedActivityTableDT(ActivityTableDT):
    def get_initial_queryset(self):
        activity = Activity.objects.get(id=self.kwargs["activity_id"])
        qs = Activity.objects.exclude(id=activity.id)
        if activity.contact and activity.client_organisation:
            qs = qs.filter(Q(contact=activity.contact) | Q(client_organisation=activity.client_organisation))
        elif activity.contact and activity.client_organisation is None:
            qs = qs.filter(contact=activity.contact)
        elif activity.client_organisation and activity.contact is None:
            qs = qs.filter(client_organisation=activity.client_organisation)
        else:
            qs = qs.none()
        qs = self._filter_on_subsidiary(qs)
        return qs.select_related("contact", "client_organisation__company", "responsible", "subsidiary")
