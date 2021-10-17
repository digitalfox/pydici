# coding: utf-8
"""
Pydici billing tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from itertools import chain

from django.db.models import Q
from django.utils.safestring import mark_safe
from django_datatables_view.base_datatable_view import BaseDatatableView

from core.decorator import PydiciFeatureMixin, PydiciNonPublicdMixin
from core.utils import to_int_or_round
from billing.views import BillingRequestMixin
from billing.models import ClientBill, SupplierBill
from people.models import Consultant
from crm.utils import get_subsidiary_from_session


class BillTableDT(PydiciNonPublicdMixin, BillingRequestMixin, BaseDatatableView):
    """Base bill table backend for datatables"""

    def _filter_on_subsidiary(self, qs):
        subsidiary = get_subsidiary_from_session(self.request)
        if subsidiary:
            qs = qs.filter(lead__subsidiary=subsidiary)
        return qs

    def get_filters(self, search):
        """Custom method to get Q filter objects that should be combined with OR keyword"""
        filters = []
        try:
            # Just try to cast to see if we have a number but use str for filter to allow proper casting by django himself
            float(search)
            filters.extend([Q(amount=search),
                            Q(amount_with_vat=search)])
        except ValueError:
            # search term is not a number
            filters.extend([Q(bill_id__icontains=search),
                            Q(state__icontains=search),
                            Q(client_deal_id__icontains=search),
                            Q(lead__deal_id__icontains=search),
                            Q(lead__client_deal_id__icontains=search),
                            Q(lead__name__icontains=search),
                            Q(lead__subsidiary__name__icontains=search),
                            Q(lead__responsible__name__icontains=search),
                            Q(lead__client__organisation__company__name__icontains=search)])
        return filters

    def filter_queryset(self, qs):
        """ simple search on some attributes"""
        search = self.request.GET.get('search[value]', None)
        qs = self._filter_on_subsidiary(qs)
        if search:
            filters = self.get_filters(search)
            query = Q()
            for filter in filters:
                query |= filter
            qs = qs.filter(query).distinct()
        return qs

    def render_column(self, row, column):
        if column in ("amount", "amount_with_vat"):
            return to_int_or_round(getattr(row, column), 2)
        elif column == "lead":
            if row.lead:
                return "<a href='{0}'>{1}</a>".format(row.lead.get_absolute_url(), row.lead)
            else:
                return "-"
        elif column in ("creation_date", "due_date", "payment_date"):
            attr = getattr(row, column)
            if attr:
                return attr.strftime("%d/%m/%y")
            else:
                return "-"
        elif column == "state":
            return row.get_state_display()
        elif column == "file":
            return mark_safe("""<a href='%s'><i class="bi bi-file-earmark-text"></i></a>""" % row.bill_file_url())
        elif column == "subsidiary":
            return str(row.lead.subsidiary)
        else:
            return super(BillTableDT, self).render_column(row, column)


class ClientBillInCreationTableDT(BillTableDT):
    """Client Bill tables backend for datatables"""
    columns = ("bill_id", "subsidiary", "lead", "responsible", "creation_date", "state", "amount", "amount_with_vat", "comment")
    order_columns = columns

    def get_initial_queryset(self):
        qs = ClientBill.objects.filter(state__in=("0_DRAFT", "0_PROPOSED"))
        qs = self._filter_on_subsidiary(qs)
        return qs

    def get_filters(self, search):
        filters = super(ClientBillInCreationTableDT, self).get_filters(search)
        filters.extend([
            Q(billdetail__mission__responsible__name__icontains=search)
        ])
        return filters

    def render_column(self, row, column):
        if column == "responsible":
            # Get missions and lead responsibles
            responsibles = ClientBill.objects.filter(id=row.id).values_list("billdetail__mission__responsible__id", "lead__responsible__id")
            responsibles = set(chain(*responsibles))  # flatten it
            responsibles = Consultant.objects.filter(id__in=responsibles)
            return ", ".join([str(c) for c in responsibles])
        else:
            return super(ClientBillInCreationTableDT, self).render_column(row, column)


class ClientBillArchiveTableDT(BillTableDT):
    """Client bill archive"""
    columns = ("bill_id", "subsidiary", "deal_id", "lead", "creation_date", "payment_date", "state", "amount", "amount_with_vat", "comment", "file")
    order_columns = columns
    max_display_length = 500

    def get_initial_queryset(self):
        qs = ClientBill.objects.exclude(state__in=("0_DRAFT", "0_PROPOSED"))
        qs = qs.select_related("lead")
        qs = self._filter_on_subsidiary(qs)
        return qs

    def render_column(self, row, column):
        if column == "deal_id":
            return row.lead.deal_id
        else:
            return super(ClientBillArchiveTableDT, self).render_column(row, column)


class SupplierBillArchiveTableDT(BillTableDT):
    """Supplier bill archive"""
    columns = ("bill_id", "supplier", "subsidiary", "lead","creation_date", "payment_date", "state", "amount", "amount_with_vat", "comment",  "file")
    order_columns = columns
    max_display_length = 20

    def get_initial_queryset(self):
        qs = SupplierBill.objects.all()
        qs = self._filter_on_subsidiary(qs)
        return qs

    def filter_queryset(self, qs):
        """ simple search on some attributes"""
        search = self.request.GET.get('search[value]', None)
        qs = self._filter_on_subsidiary(qs)
        if search:
            qs = qs.filter(Q(bill_id__icontains=search) |
                           Q(lead__deal_id__icontains=search) |
                           Q(lead__name__icontains=search) |
                           Q(lead__responsible__name__icontains=search) |
                           Q(lead__subsidiary__name__icontains=search) |
                           Q(lead__client__organisation__company__name__icontains=search) |
                           Q(supplier__company__name__icontains=search) |
                           Q(supplier__contact__name__icontains=search)
                           )
        return qs
