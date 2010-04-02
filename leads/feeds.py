# coding: utf-8
"""Atom feeds
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from django.contrib.syndication.feeds import Feed
from django.utils.feedgenerator import Atom1Feed

from pydici.leads.models import Consultant, Lead
import pydici.settings

class LeadFeed(Feed):
    feed_type = Atom1Feed
    link = pydici.settings.LEADS_WEB_LINK_ROOT
    description_template = "leads/lead_mail.html"
    title_template = "leads/feed_title.txt"

    def item_pubdate(self, item):
        return item.update_date

    def item_guid(self, item):
        return "%s-%s" % (item.id, item.update_date)

class LatestLeads(LeadFeed):
    title = "Les leads récents"
    description = "Les 20 derniers leads modifiés"

    def items(self):
        return Lead.objects.order_by('-update_date')[:50]

class NewLeads(LeadFeed):
    title = "Les nouveaux Leads"
    description = "Les 20 derniers leads crées"

    def item_guid(self, item):
        """Overload std guid to make it unchanged when lead is updated"""
        return "%s-%s" % (item.id, item.creation_date)

    def items(self):
        return Lead.objects.order_by('-creation_date')[:50]

class WonLeads(LeadFeed):
    title = "Les leads gagnés"
    description = "Les 20 derniers leads gagnés"

    def items(self):
        return Lead.objects.filter(state="WON").order_by('-update_date')[:50]

class MyLatestLeads(LeadFeed):
    title = "Mes Leads"
    description = "Tous les leads actifs dont je suis responsable ou ressource pressentie"

    def items(self):
        consultants = Consultant.objects.filter(trigramme__iexact=self.request.user.username)
        if consultants:
            consultant = consultants[0]
            return set(consultant.lead_responsible.active() | consultant.lead_set.active())
        else:
            return []

class AllChanges(LeadFeed):
    pass
