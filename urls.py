# -*- coding: UTF-8 -*-
"""URL dispatcher
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: BSD
"""
#
from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template

admin.autodiscover()


# Feeds definition
from pydici.leads.feeds import LatestLeads, NewLeads, MyLatestLeads, AllChanges, WonLeads

feeds = {
        "latest": LatestLeads,
        "new" :   NewLeads,
        "won" :   WonLeads,
        "mine":   MyLatestLeads,
        "all" :   AllChanges
        }

urlpatterns = patterns('',
    # Default to leads index
    (r'^$', 'pydici.leads.views.index'),

    # Admin
    (r'^leads/admin/doc/', include('django.contrib.admindocs.urls')),
     (r'^leads/admin/(.*)', admin.site.root),

    # Lead application
    (r'^leads/$', 'pydici.leads.views.index'),
    (r'^leads/review', 'pydici.leads.views.review'),
    (r'^leads/IA_stats', 'pydici.leads.views.IA_stats'),
    (r'^leads/forbiden',  direct_to_template, {'template': 'forbiden.html'}),
    (r'^leads/csv/(.*)', 'pydici.leads.views.csv_export'),
    (r'^leads/(?P<lead_id>\d+)/$', 'pydici.leads.views.detail'),
    (r'^leads/sendmail/(?P<lead_id>\d+)/$', 'pydici.leads.views.mail_lead'),
    (r'^leads/mail/text', 'pydici.leads.views.summary_mail', { "html" : False }),
    (r'^leads/mail/html', 'pydici.leads.views.summary_mail', { "html" : True  }),
    (r'^leads/graph/pie', 'pydici.leads.views.graph_stat_pie'),
    (r'^leads/graph/bar', 'pydici.leads.views.graph_stat_bar'),
    (r'^leads/graph/salesmen', 'pydici.leads.views.graph_stat_salesmen'),
    (r'^leads/media/leads/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': '/home/fox/prog/workspace/pydici/media/leads/'}),

    # Feeds
    (r'^leads/feeds/(?P<url>.*)/$', 'django.contrib.syndication.views.feed',
            {'feed_dict': feeds})
)
