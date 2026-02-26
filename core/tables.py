# coding: utf-8
"""
Pydici core tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.db.models import Q
from django.urls import reverse

from django_datatables_view.base_datatable_view import BaseDatatableView
from core.models import Tag

from core.decorator import PydiciFeatureMixin, PydiciNonPublicdMixin


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
