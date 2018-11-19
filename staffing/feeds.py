# coding: utf-8
"""Atom feeds
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed
from django.utils.translation import ugettext as _
from django.core import urlresolvers

from staffing.models import Staffing, Mission
from people.models import Consultant


class StaffingFeed(Feed):
    feed_type = Atom1Feed
    description_template = "staffing/feed_staffing_content.html"
    title_template = "staffing/feed_staffing_title.txt"

    def link(self):
        return urlresolvers.reverse("core:index")

    def item_pubdate(self, item):
        return item.update_date

    def item_guid(self, item):
        return "%s-%s" % (item.id, item.update_date)

    def item_author_name(self, item):
        if item.last_user:
            return item.last_user


class LatestStaffing(StaffingFeed):
    title = _("Latest staffing update")
    description = _("Last consultant forecast staffing updated or created")

    def items(self):
        return Staffing.objects.order_by('-update_date')[:50]


class MyLatestStaffing(StaffingFeed):
    title = _("My lastest staffing update")
    description = _("Last forecast staffing updated or created about myself")

    def get_object(self, request, *args, **kwargs):
        # Save request object for further use in items method.
        self.request = request
        return StaffingFeed.get_object(self, request, *args, **kwargs)

    def items(self):
        consultants = Consultant.objects.filter(trigramme__iexact=self.request.user.username)
        if consultants:
            consultant = consultants[0]
            return consultant.staffing_set.order_by("-update_date")[:50]
        else:
            return []


class ArchivedMission(Feed):
    feed_type = Atom1Feed
    # description_template = "staffing/feed_content.html"
    # title_template = "staffing/feed_title.txt"

    def link(self):
        return urlresolvers.reverse("core:index")

    def item_pubdate(self, item):
        return item.update_date

    def item_guid(self, item):
        return "%s-%s" % (item.id, item.update_date)

    def item_author_name(self, item):
        if item.lead and item.lead.responsible:
            return item.lead.responsible

    def items(self):
        return Mission.objects.filter(active=False).order_by('-update_date')[:50]
