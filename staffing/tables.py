# coding: utf-8
"""
Pydici staffing tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import gettext as _
from django.template.loader import get_template
from django.db.models import Q
from django.utils.safestring import mark_safe
from django.utils.html import escape

from django_datatables_view.base_datatable_view import BaseDatatableView

from staffing.models import Mission
from core.decorator import PydiciFeatureMixin, PydiciNonPublicdMixin
from crm.utils import get_subsidiary_from_session


class MissionsViewsMixin(PydiciNonPublicdMixin, PydiciFeatureMixin):
    """Internal access to mission data for CB views"""
    pydici_feature = "staffing"


class MissionsTableDT(MissionsViewsMixin, BaseDatatableView):
    """Missions tables backend for datatables"""
    columns = ("pk", "subsidiary", "responsible", "nature", "mission_id", "price", "billing_mode", "marketing_product", "no_forecast", "old_forecast", "archived_date")
    order_columns = columns
    max_display_length = 500
    archiving_template = get_template("staffing/_mission_table_archive_column.html")
    ko_sign = mark_safe("""<i class="bi bi-exclamation-triangle" style="color:red"></i>""")
    ok_sign = mark_safe("""<i class="bi bi-check" style="color:green"></i>""")

    def _filter_on_subsidiary(self, qs):
        subsidiary = get_subsidiary_from_session(self.request)
        if subsidiary:
            qs = qs.filter(subsidiary=subsidiary)
        return qs

    def _filter_on_consultant(self, qs):
        """Filter on consultant based on timesheet"""
        consultant_id = self.kwargs.get("consultant_id", None)
        if consultant_id:
            qs = qs.filter(timesheet__consultant_id=consultant_id).distinct()
        return qs

    def get_initial_queryset(self):
        return Mission.objects.all().select_related("lead__client__organisation__company", "subsidiary")

    def filter_queryset(self, qs):
        """ simple search on some attributes"""
        search = self.request.GET.get(u'search[value]', None)
        qs = self._filter_on_subsidiary(qs)
        qs = self._filter_on_consultant(qs)
        if search:
            qs = qs.filter(Q(deal_id__icontains=search) |
                           Q(description__icontains=search) |
                           Q(description__icontains=search) |
                           Q(subsidiary__name__icontains=search) |
                           Q(lead__name__icontains=search) |
                           Q(lead__responsible__name__icontains=search) |
                           Q(lead__mission__responsible__name__icontains=search) |
                           Q(lead__description__icontains=search) |
                           Q(lead__tags__name__iexact=search) |
                           Q(lead__client__contact__name__icontains=search) |
                           Q(lead__client__organisation__company__name__icontains=search) |
                           Q(lead__client__organisation__name__iexact=search) |
                           Q(lead__deal_id__icontains=search) |
                           Q(marketing_product__description__icontains=search)
                           ).distinct()
        return qs

    def render_column(self, row, column):
        if column == "pk":
            return "<a href='{0}'>{1}</a>".format(row.get_absolute_url(), escape(row))
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
        elif column == "archived_date":
            return self.archiving_template.render(context={"row": row}, request=self.request)
        elif column == "mission_id":
            return row.mission_id()
        elif column == "marketing_product":
            if row.nature == "PROD":
                return row.marketing_product.description if row.marketing_product else _("To be defined")
            else:
                return "-"
        else:
            return super(MissionsTableDT, self).render_column(row, column)


class ActiveMissionsTableDT(MissionsTableDT):
    """Active missions table backend for datatables"""
    def get_initial_queryset(self):
        return Mission.objects.filter(active=True).select_related("lead__client__organisation__company", "subsidiary")


class ClientCompanyActiveMissionsTablesDT(MissionsTableDT):
    def get_initial_queryset(self):
        return Mission.objects.filter(active=True, lead__client__organisation__company__id=self.kwargs["clientcompany_id"]).select_related("lead__client__organisation__company", "subsidiary")