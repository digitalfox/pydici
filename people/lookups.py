# coding:utf-8
"""
Ajax custom lookup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from people.models import Consultant, SalesMan
from django.db.models import Q
from ajax_select import LookupChannel


class PeopleLookup(LookupChannel):
    def get_query(self, q, request):
        """ return a query set.  you also have access to request.user if needed """
        return self.model.objects.filter(active=True).filter(Q(name__icontains=q) |
                                                              Q(trigramme__icontains=q))

    def format_item_display(self, people):
        """ (HTML) formatted item for displaying item in the selected deck area """
        return u"%s (%s)" % (people.name, people.trigramme)


class ConsultantLookup(PeopleLookup):
    model = Consultant


class InternalConsultantLookup(PeopleLookup):
    model = Consultant

    def get_query(self, q, request):
        """Supersede query set by filtering out subcontractors"""
        return super(InternalConsultantLookup, self).get_query(q, request).filter(subcontractor=False)


class SalesmanLookup(PeopleLookup):
    model = SalesMan
