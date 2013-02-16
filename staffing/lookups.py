# coding:utf-8
"""
Ajax custom lookup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from pydici.staffing.models import Mission
from django.db.models import Q

class MissionLookup(object):
    def get_query(self, q, request):
        """ return a query set.  you also have access to request.user if needed """
        qs = Mission.objects.filter(active=True)  # Remove archived mission
        # Get mission with lead by lead and client name
        qs = qs.filter(Q(deal_id__icontains=q) |
                       Q(description__icontains=q) |
                       Q(lead__name__icontains=q) |
                       Q(lead__deal_id__icontains=q) |
                       Q(lead__client__organisation__name__icontains=q) |
                       Q(lead__client__organisation__company__name__icontains=q))

        # Add mission without lead (don't do that in a single qs as FK can be null)
        qs = qs | Mission.objects.filter(active=True).filter(description__icontains=q)

        return qs

    def format_result(self, mission):
        """ the search results display in the dropdown menu.  may contain html and multiple-lines. will remove any |  """
        return mission.full_name()

    def format_item(self, mission):
        """ the display of a currently selected object in the area below the search box. html is OK """
        return unicode(mission)

    def get_objects(self, ids):
        """ given a list of ids, return the objects ordered as you would like them on the admin page.
            this is for displaying the currently selected items (in the case of a ManyToMany field)
        """
        return Mission.objects.filter(pk__in=ids).order_by('lead', 'description')
