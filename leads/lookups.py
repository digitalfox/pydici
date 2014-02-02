# coding:utf-8
"""
Ajax custom lookup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from leads.models import Lead
from django.db.models import Q
from ajax_select import LookupChannel


class LeadLookup(LookupChannel):
    model = Lead

    def get_query(self, q, request):
        """ return a query set.  you also have access to request.user if needed """
        qs = Lead.objects.filter(state="WON")
        # Get lead with name and client name
        qs = qs.filter(Q(name__icontains=q) |
                       Q(deal_id__icontains=q) |
                       Q(client__organisation__name__icontains=q) |
                       Q(client__organisation__company__name__icontains=q))
        return qs

    def format_item_display(self, lead):
        """ (HTML) formatted item for displaying item in the selected deck area """
        return u"%s (%s)" % (lead, lead.deal_id)
