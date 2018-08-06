# coding: utf-8
"""
Pydici billing tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.db.models import Q
from django_datatables_view.base_datatable_view import BaseDatatableView

from core.decorator import PydiciFeatureMixin, PydiciNonPublicdMixin
from crm.views import ThirdPartyMixin
from billing.models import ClientBill


class ClientBillTableDT(ThirdPartyMixin, BaseDatatableView):
    """Client Bill tables backend for datatables"""
    columns = ("bill_id", "lead", "creation_date", "state", "amount", "amount_with_vat", "comment")
    order_columns = columns
    max_display_length = 20


    def get_initial_queryset(self):
        return ClientBill.objects.filter(state__in=("0_DRAFT", "0_PROPOSED"))

    def filter_queryset(self, qs):
        """ simple search on some attributes"""
        search = self.request.GET.get(u'search[value]', None)
        if search:
            qs = qs.filter(Q(bill_id__icontains=search) |
                           Q(lead__deal_id__icontains=search) |
                           Q(lead__description__icontains=search) |
                           Q(lead__name__icontains=search) |
                           Q(lead__client__organisation__company__name__icontains=search)
                           )
        return qs

