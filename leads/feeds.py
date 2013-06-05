# coding: utf-8
"""Atom feeds
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed
from django.utils.translation import ugettext as _

from leads.models import Consultant, Lead
from django.core import urlresolvers


class LeadFeed(Feed):
    feed_type = Atom1Feed
    description_template = "leads/lead_mail.html"
    title_template = "leads/feed_title.txt"

    def link(self):
        return urlresolvers.reverse("pydici.core.views.index")

    def item_link(self, obj):
        url = urlresolvers.reverse("pydici.leads.views.detail", args=[obj.id])
        return  self.request.build_absolute_uri(url)

    def item_pubdate(self, item):
        return item.update_date

    def item_guid(self, item):
        return "%s-%s" % (item.id, item.update_date)

    def item_author_name(self, item):
        return item.responsible


class LatestLeads(LeadFeed):
    title = _("Latest leads")
    description = _("Last modified or created leads")

    def items(self):
        return Lead.objects.order_by('-update_date')[:50]

class NewLeads(LeadFeed):
    title = _("New leads")
    description = _("Last new lead created")

    def item_guid(self, item):
        """Overload std guid to make it unchanged when lead is updated"""
        return "%s-%s" % (item.id, item.creation_date)

    def items(self):
        return Lead.objects.order_by('-creation_date')[:50]

class WonLeads(LeadFeed):
    title = _("Won leads")
    description = _("Last won leads")

    def items(self):
        return Lead.objects.filter(state="WON").order_by('-update_date')[:50]

class MyLatestLeads(LeadFeed):
    title = _("My leads")
    description = _("Last active leads that I am responsible or resource")

    def items(self):
        consultants = Consultant.objects.filter(trigramme__iexact=self.request.user.username)
        if consultants:
            consultant = consultants[0]
            return set(consultant.lead_responsible.active() | consultant.lead_set.active())
        else:
            return []
