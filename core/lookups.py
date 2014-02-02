# coding:utf-8
"""
Ajax custom lookup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib.auth.models import User
from django.db.models import Q
from ajax_select import LookupChannel


class UserLookup(LookupChannel):
    model = User

    def get_query(self, q, request):
        """ return a query set.  you also have access to request.user if needed """
        qs = User.objects.filter(is_active=True)
        # Get user from firstname, lastname or username
        qs = qs.filter(Q(username__icontains=q) |
                       Q(first_name__icontains=q) |
                       Q(last_name__icontains=q))
        return qs

    def get_result(self, user):
        """ The text result of autocompleting the entered query """
        return user.username

    def format_match(self, user):
        """ (HTML) formatted item for displaying item in the dropdown """
        return u"%s %s" % (user.first_name, user.last_name)
