# coding: utf-8
"""
Pydici crm tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.db.models import Q
from django_datatables_view.base_datatable_view import BaseDatatableView

from core.decorator import PydiciNonPublicdMixin
from crm.views import ThirdPartyMixin
from crm.models import Contact, BusinessBroker, Supplier


class ContactTableDT(PydiciNonPublicdMixin, ThirdPartyMixin, BaseDatatableView):
    """Contact tables backend for datatables"""
    columns = ("name", "companies", "function", "email", "phone", "mobile_phone", "contacts")
    order_columns = columns
    max_display_length = 500


    def get_initial_queryset(self):
        return Contact.objects.all().prefetch_related("contact_points")

    def filter_queryset(self, qs):
        """ simple search on some attributes"""
        search = self.request.GET.get('search[value]', None)
        if search:
            qs = qs.filter(Q(name__icontains=search) |
                           Q(function__icontains=search) |
                           Q(email__icontains=search) |
                           Q(mobile_phone__icontains=search) |
                           Q(fax__icontains=search) |
                           Q(contact_points__name__icontains=search) |
                           Q(contact_points__trigramme__icontains=search) |
                           Q(phone__icontains=search) |
                           Q(client__organisation__company__name__icontains=search)
                           ).distinct()
        return qs

    def render_column(self, row, column):
        if column == "companies":
            return row.companies(html=True)
        elif column == "contacts":
            return ", ".join([c.name for c in row.contact_points.all()])
        else:
            return super(ContactTableDT, self).render_column(row, column)


class BusinessBrokerTableDT(PydiciNonPublicdMixin, ThirdPartyMixin, BaseDatatableView):
    """Business broker tables backend for datatables"""
    columns = ("company", "contact", "billing_name")
    order_columns = columns
    max_display_length = 500

    def get_initial_queryset(self):
        return BusinessBroker.objects.all()

    def filter_queryset(self, qs):
        """ simple search on some attributes"""
        search = self.request.GET.get('search[value]', None)
        if search:
            qs = qs.filter(Q(contact__name__icontains=search) |
                           Q(contact__contact_points__name__icontains=search) |
                           Q(company__name__icontains=search)
                           ).distinct()
        return qs


class SupplierTableDT(PydiciNonPublicdMixin, ThirdPartyMixin, BaseDatatableView):
    """Supplier tables backend for datatables"""
    columns = ("company", "contact")
    order_columns = columns
    max_display_length = 500

    def get_initial_queryset(self):
        return Supplier.objects.all()

    def filter_queryset(self, qs):
        """ simple search on some attributes"""
        search = self.request.GET.get('search[value]', None)
        if search:
            qs = qs.filter(Q(contact__name__icontains=search) |
                           Q(company__name__icontains=search)
                           ).distinct()
        return qs
