# coding: utf-8

from django.contrib.syndication.feeds import Feed

from pydici.leads.models import Lead
import pydici.settings

class LatestLeads(Feed):
    title = "Les leads récents"
    link = pydici.settings.LEADS_MAIL_LINK_ROOT
    description = "Les 20 derniers leads modifiés"

    description_template="leads/lead_mail.html"

    def items(self):
        return Lead.objects.order_by('-update_date')[:20]


class NewLeads(Feed):
    pass

class MyLatestLeads(Feed):
    pass

class AllChanges(Feed):
    pass