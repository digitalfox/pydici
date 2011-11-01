# coding:utf-8
"""
Ajax custom lookup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from pydici.people.models import Consultant, SalesMan
from django.db.models import Q

class PeopleLookup(object):
    def get_query(self, q, request):
        """ return a query set.  you also have access to request.user if needed """
        return self.People.objects.filter(active=True).filter(Q(name__icontains=q) |
                                                              Q(trigramme__icontains=q))

    def format_result(self, people):
        """ the search results display in the dropdown menu.  may contain html and multiple-lines. will remove any |  """
        return u"%s (%s)" % (people.name, people.trigramme)

    def format_item(self, people):
        """ the display of a currently selected object in the area below the search box. html is OK """
        return unicode(people)

    def get_objects(self, ids):
        """ given a list of ids, return the objects ordered as you would like them on the admin page.
            this is for displaying the currently selected items (in the case of a ManyToMany field)
        """
        return self.People.objects.filter(pk__in=ids).order_by('name')

class ConsultantLookup(PeopleLookup):
    People = Consultant

class InternalConsultantLookup(PeopleLookup):
    People = Consultant
    def get_query(self, q, request):
        """Supersede query set by filtering out subcontractors"""
        return super(InternalConsultantLookup, self).get_query(q, request).filter(subcontractor=False)

class SalesmanLookup(PeopleLookup):
    People = SalesMan
