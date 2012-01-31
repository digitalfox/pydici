# coding:utf-8
"""
Ajax custom lookup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from pydici.crm.models import Client, BusinessBroker
from django.db.models import Q


class ClientLookup(object):
    def get_query(self, q, request):
        """ return a query set.  you also have access to request.user if needed """
        return Client.objects.filter(Q(organisation__name__icontains=q) |
                                     Q(organisation__company__name__icontains=q) |
                                     Q(contact__name__icontains=q))

    def format_result(self, client):
        """ the search results display in the dropdown menu.  may contain html and multiple-lines. will remove any |  """
        return unicode(client)

    def format_item(self, client):
        """ the display of a currently selected object in the area below the search box. html is OK """
        return unicode(client)

    def get_objects(self, ids):
        """ given a list of ids, return the objects ordered as you would like them on the admin page.
            this is for displaying the currently selected items (in the case of a ManyToMany field)
        """
        return Client.objects.filter(pk__in=ids).order_by('organisation', 'contact')


class BusinessBrokerLookup(object):
    def get_query(self, q, request):
        """ return a query set.  you also have access to request.user if needed """
        return BusinessBroker.objects.filter(Q(contact__name__icontains=q) |
                                             Q(company__name__icontains=q))

    def format_result(self, broker):
        """ the search results display in the dropdown menu.  may contain html and multiple-lines. will remove any |  """
        return unicode(broker)

    def format_item(self, broker):
        """ the display of a currently selected object in the area below the search box. html is OK """
        return unicode(broker)

    def get_objects(self, ids):
        """ given a list of ids, return the objects ordered as you would like them on the admin page.
            this is for displaying the currently selected items (in the case of a ManyToMany field)
        """
        return BusinessBroker.objects.filter(pk__in=ids).order_by("company", "contact")
