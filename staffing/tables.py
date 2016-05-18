# coding: utf-8
"""
Pydici staffing tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import ugettext as _
from django.template.loader import get_template
from django.db.models import Q
from django.utils.safestring import mark_safe

from django_datatables_view.base_datatable_view import BaseDatatableView

from staffing.models import Mission
from core.decorator import PydiciFeatureMixin, PydiciNonPublicdMixin

class MissionsViewsMixin(PydiciNonPublicdMixin, PydiciFeatureMixin):
    """Internal access to mission data for CB views"""
    pydici_feature = "staffing"


class MissionsTableDT(MissionsViewsMixin, BaseDatatableView):
    """Missions tables backend for datatables"""
    columns = ("pk", "subsidiary", "responsible", "nature", "mission_id", "price", "no_forecast", "old_forecast", "archive")
    order_columns = columns
    max_display_length = 500
    archiving_template = get_template("staffing/_mission_table_archive_column.html")
    ko_sign = mark_safe("""<span class="glyphicon glyphicon-warning-sign" style="color:red"></span>""")
    ok_sign = mark_safe("""<span class="glyphicon glyphicon-ok" style="color:green"></span>""")

    def get_initial_queryset(self):
        #TODO: declare explicit join with select_related()
        return Mission.objects.all()

    def filter_queryset(self, qs):
        """ simple search on some attributes"""
        search = self.request.GET.get(u'search[value]', None)
        if search:
            qs = qs.filter(Q(deal_id__icontains=search) |
                           Q(description__icontains=search) |
                           Q(description__icontains=search) |
                           Q(lead__name__icontains=search) |
                           Q(lead__description__icontains=search) |
                           Q(lead__tags__name__iexact=search) |
                           Q(lead__client__contact__name__icontains=search) |
                           Q(lead__client__organisation__company__name__icontains=search) |
                           Q(lead__client__organisation__name__iexact=search) |
                           Q(lead__deal_id__icontains=search)
                           )
        return qs

    def render_column(self, row, column):
        if column == "pk":
            return u"<a href='{0}'>{1}</a>".format(row.get_absolute_url(), unicode(row))
        elif column == "no_forecast":
            if row.no_more_staffing_since():
                return self.ko_sign
            else:
                return self.ok_sign
        elif column == "old_forecast":
            if row.no_staffing_update_since():
                return self.ko_sign
            else:
                return self.ok_sign
        elif column == "archive":
            return self.archiving_template.render({"row": row})
        elif column == "mission_id":
            return row.mission_id()
        else:
            return super(MissionsTableDT, self).render_column(row, column)

class ActiveMissionsTableDT(MissionsTableDT):
    """Active missions table backend for datatables"""
    def get_initial_queryset(self):
        # TODO: declare explicit join with select_related()
        return Mission.objects.filter(active=True)