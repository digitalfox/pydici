# coding: utf-8

from django.contrib.syndication.feeds import Feed

from pydici.leads.models import Lead
import pydici.settings

class LeadFeed(Feed):
    link=pydici.settings.LEADS_MAIL_LINK_ROOT
    description_template="leads/lead_mail.html"
    title_template="leads/feed_title.txt"

class LatestLeads(LeadFeed):
    title="Les leads récents"
    description="Les 20 derniers leads modifiés"

    def items(self):
        return Lead.objects.order_by('-update_date')[:20]

class NewLeads(LeadFeed):
    title="Les nouveaux Leads"
    description="Les 20 derniers leads crées"

    def items(self):
        return Lead.objects.order_by('-creation_date')[:20]

class WonLeads(LeadFeed):
    title="Les leads gagnés"
    description="Les 20 derniers leads gagnés"

    def items(self):
        return Lead.objects.filter(state="WIN").order_by('-update_date')[:20]

class MyLatestLeads(LeadFeed):
    pass

class AllChanges(LeadFeed):
    pass