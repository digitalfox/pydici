# coding:utf-8
"""
Ajax custom lookup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from crm.models import Client, BusinessBroker, Supplier, MissionContact
from django.db.models import Q
from ajax_select import LookupChannel


class ClientLookup(LookupChannel):
    model = Client

    def get_query(self, q, request):
        """ return a query set.  you also have access to request.user if needed """
        return Client.objects.filter(Q(organisation__name__icontains=q) |
                                     Q(organisation__company__name__icontains=q) |
                                     Q(contact__name__icontains=q))


class ThirdPartyLookup(LookupChannel):
    """Common lookup for all models based on couple (company, contact)"""
    def get_query(self, q, request):
        """ return a query set.  you also have access to request.user if needed """
        return self.model.objects.filter(Q(contact__name__icontains=q) |
                                              Q(company__name__icontains=q))


class BusinessBrokerLookup(ThirdPartyLookup):
    model = BusinessBroker


class SupplierLookup(ThirdPartyLookup):
    model = Supplier


class MissionContactLookup(ThirdPartyLookup):
    model = MissionContact
