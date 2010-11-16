# coding: utf-8
"""Atom feeds
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from django.contrib.syndication.feeds import Feed, FeedDoesNotExist
from django.utils.feedgenerator import Atom1Feed

from pydici.staffing.models import Staffing
from pydici.people.models import Consultant

import pydici.settings
from django.core import urlresolvers

class StaffingFeed(Feed):
    feed_type = Atom1Feed
    description_template = "staffing/feed_content.html"
    title_template = "staffing/feed_title.txt"

    def link(self):
        return urlresolvers.reverse("pydici.core.views.index")

    def item_link(self, obj):
        url = urlresolvers.reverse("pydici.staffing.views.consultant_staffing", args=[obj.consultant.id])
        return  self.request.build_absolute_uri(url)

    def item_pubdate(self, item):
        return item.update_date

    def item_guid(self, item):
        return "%s-%s" % (item.id, item.update_date)

class LatestStaffing(StaffingFeed):
    title = "Les dernières mises à jour de staffing"
    description = "Les derniers staffing crées/modifiés"

    def items(self):
        return Staffing.objects.order_by('-update_date')[:50]

class MyLatestStaffing(StaffingFeed):
    title = "Mes prévisions de staffing"
    description = "Toutes les prévisions de staffing me concernant"

    def items(self):
        consultants = Consultant.objects.filter(trigramme__iexact=self.request.user.username)
        if consultants:
            consultant = consultants[0]
            return consultant.staffing_set.order_by("-update_date")[:50]
        else:
            return []
