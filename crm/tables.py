# coding: utf-8
"""
Pydici crm tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.template.loader import get_template
from django.db.models import Q
from django_datatables_view.base_datatable_view import BaseDatatableView

from core.decorator import PydiciFeatureMixin, PydiciNonPublicdMixin
from crm.views import ThirdPartyMixin
from crm.models import Contact


class ContactTableDT(ThirdPartyMixin, BaseDatatableView):
    """Contact tables backend for datatables"""
    columns = ("name", "companies", "function", "email", "phone", "mobile_phone", "fax")
    order_columns = columns
    max_display_length = 500


    def get_initial_queryset(self):
        #TODO: declare explicit join with select_related()
        return Contact.objects.all()

    def filter_queryset(self, qs):
        """ simple search on some attributes"""
        search = self.request.GET.get(u'search[value]', None)
        if search:
            qs = qs.filter(Q(name__icontains=search) |
                           Q(function__icontains=search) |
                           Q(email__icontains=search) |
                           Q(mobile_phone__icontains=search) |
                           Q(fax__icontains=search) |
                           Q(phone__icontains=search) |
                           Q(client__organisation__company__name__icontains=search)
                           ).distinct()
        return qs

    def render_column(self, row, column):
        if column == "pk":
            return u"<a href='{0}'>{1}</a>".format(row.get_absolute_url(), unicode(row))
        elif column == "companies":
            return row.companies(html=True)
        else:
            return super(ContactTableDT, self).render_column(row, column)

