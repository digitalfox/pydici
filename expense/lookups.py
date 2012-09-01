# coding:utf-8
"""
Ajax custom lookup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils import formats

from pydici.expense.models import Expense
from django.db.models import Q


class ChargeableExpenseLookup(object):
    def get_query(self, q, request):
        """ return a query set.  you also have access to request.user if needed """
        # Only return chargeable expenses that are not already been associated to a client bill
        return Expense.objects.filter(chargeable=True, clientbill=None).filter(Q(description__icontains=q) |
                                                                               Q(comment__icontains=q) |
                                                                               Q(lead__name__icontains=q) |
                                                                               Q(lead__deal_id__icontains=q) |
                                                                               Q(lead__client__organisation__company__name__icontains=q))

    def format_result(self, expense):
        """ the search results display in the dropdown menu.  may contain html and multiple-lines. will remove any |  """
        return u"%s (%s %s) - %s" % (expense, expense.user.first_name, expense.user.last_name,
                                     formats.date_format(expense.expense_date))

    def format_item(self, expense):
        """ the display of a currently selected object in the area below the search box. html is OK """
        return u"%s (%s %s) - %s" % (expense, expense.user.first_name, expense.user.last_name,
                                     formats.date_format(expense.expense_date))

    def get_objects(self, ids):
        """ given a list of ids, return the objects ordered as you would like them on the admin page.
            this is for displaying the currently selected items (in the case of a ManyToMany field)
        """
        return Expense.objects.filter(pk__in=ids).order_by("expense_date")
