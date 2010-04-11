# -*- coding: UTF-8 -*-
"""URL dispatcher
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""
# Django import
from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template, redirect_to

admin.autodiscover()

# Config to get admin conctat
import pydici.settings
admin_contact = { "ADMINS" : pydici.settings.ADMINS }

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
    (r'^leads/admin/', include(admin.site.urls)),

    # Ajax select
    (r'^ajax_select/', include('ajax_select.urls')),

    # Lead application
    (r'^leads/$', 'pydici.leads.views.index'),
    (r'^leads/review', 'pydici.leads.views.review'),
    (r'^leads/pdcreview/?$', 'pydici.leads.views.pdc_review'),
    (r'^leads/pdcreview/(?P<year>\d+)/(?P<month>\d+)/?$', 'pydici.leads.views.pdc_review'),
    (r'^leads/IA_stats', 'pydici.leads.views.IA_stats'),
    (r'^leads/forbiden', direct_to_template, {'template': 'forbiden.html', 'extra_context': admin_contact}),
    (r'^leads/help', redirect_to, {'url': pydici.settings.LEADS_HELP_PAGE}),
    (r'^leads/csv/(.*)', 'pydici.leads.views.csv_export'),
    (r'^leads/(?P<lead_id>\d+)/$', 'pydici.leads.views.detail'),
    (r'^leads/mission/$', 'pydici.leads.views.missions'),
    (r'^leads/mission/all', 'pydici.leads.views.missions', { "onlyActive" : False }),
    (r'^leads/mission/(?P<mission_id>\d+)/$', 'pydici.leads.views.mission_staffing'),
    (r'^leads/mission/(?P<mission_id>\d+)/deactivate$', 'pydici.leads.views.deactivate_mission'),
    (r'^leads/consultant/(?P<consultant_id>\d+)/$', 'pydici.leads.views.consultant_staffing'),
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
