# coding:utf-8
"""
Ajax custom lookup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib.auth.models import User
from django.db.models import Q

class UserLookup(object):
    def get_query(self, q, request):
        """ return a query set.  you also have access to request.user if needed """
        qs = User.objects.filter(is_active=True)
        # Get user from firstname, lastname or username
        qs = qs.filter(Q(username__icontains=q) |
                       Q(first_name__icontains=q) |
                       Q(last_name__icontains=q))
        return qs

    def format_result(self, user):
        """ the search results display in the dropdown menu.  may contain html and multiple-lines. will remove any |  """
        return u"%s %s" % (user.first_name, user.last_name)

    def format_item(self, user):
        """ the display of a currently selected object in the area below the search box. html is OK """
        return user.username

    def get_objects(self, ids):
        """ given a list of ids, return the objects ordered as you would like them on the admin page.
            this is for displaying the currently selected items (in the case of a ManyToMany field)
        """
        return User.objects.filter(pk__in=ids).order_by("username")
