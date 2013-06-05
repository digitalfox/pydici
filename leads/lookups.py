# coding:utf-8
"""
Ajax custom lookup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from leads.models import Lead
from django.db.models import Q


class LeadLookup(object):
    def get_query(self, q, request):
        """ return a query set.  you also have access to request.user if needed """
        qs = Lead.objects.filter(state="WON")
        # Get lead with name and client name
        qs = qs.filter(Q(name__icontains=q) |
                       Q(deal_id__icontains=q) |
                       Q(client__organisation__name__icontains=q) |
                       Q(client__organisation__company__name__icontains=q))
        return qs

    def format_result(self, lead):
        """ the search results display in the dropdown menu.  may contain html and multiple-lines. will remove any |  """
        return u"%s (%s)" % (lead, lead.deal_id)

    def format_item(self, lead):
        """ the display of a currently selected object in the area below the search box. html is OK """
        return unicode(lead)

    def get_objects(self, ids):
        """ given a list of ids, return the objects ordered as you would like them on the admin page.
            this is for displaying the currently selected items (in the case of a ManyToMany field)
        """
        return Lead.objects.filter(pk__in=ids).order_by("name")
