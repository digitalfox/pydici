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


pydici_patterns = patterns('',
    # Admin
    (r'^leads/admin/doc/', include('django.contrib.admindocs.urls')),
    (r'^leads/admin/', include(admin.site.urls)),

    # Ajax select
    (r'^ajax_select/', include('ajax_select.urls')),
)

pydici_patterns += patterns('',
    # Direct to template and direct pages
    url(r'^leads/forbiden', direct_to_template, {'template': 'forbiden.html', 'extra_context': admin_contact}, name='forbiden'),
    url(r'^leads/help', redirect_to, {'url': pydici.settings.LEADS_HELP_PAGE}, name='help'),

    # Media
    (r'^leads/media/leads/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': '/home/fox/prog/workspace/pydici/media/leads/'}),

    # Feeds
    url(r'^leads/feeds/(?P<url>.*)/$', 'django.contrib.syndication.views.feed',
            {'feed_dict': feeds}, name='feed'),
)

pydici_patterns += patterns('pydici.core.views',
    # core module
    (r'^$', 'index'),
    url(r'^leads/$', 'index', name='index'),
)

pydici_patterns += patterns('pydici.leads.views',
    # Lead module
    (r'^leads/review', 'review'),
    (r'^leads/IA_stats', 'IA_stats'),
    (r'^leads/csv/(?P<target>.*)', 'csv_export'),
    (r'^leads/(?P<lead_id>\d+)/$', 'detail'),
    (r'^leads/sendmail/(?P<lead_id>\d+)/$', 'mail_lead'),
    url(r'^leads/mail/text', 'summary_mail', { "html" : False }, name="lead-mail-text"),
    url(r'^leads/mail/html', 'summary_mail', { "html" : True  }, name="lead-mail-html"),
    (r'^leads/graph/pie', 'graph_stat_pie'),
    (r'^leads/graph/bar', 'graph_stat_bar'),
    (r'^leads/graph/salesmen', 'graph_stat_salesmen'),
)

pydici_patterns += patterns('pydici.staffing.views',
    # Staffing module
    url(r'^leads/pdcreview/?$', 'pdc_review', name='pdcreview-index'),
    url(r'^leads/pdcreview/(?P<year>\d+)/(?P<month>\d+)/?$', 'pdc_review', name='pdcreview'),
    url(r'^leads/mission/$', 'missions', name='missions'),
    url(r'^leads/mission/all', 'missions', { 'onlyActive' : False }, 'all-missions'),
    (r'^leads/mission/(?P<mission_id>\d+)/$', 'mission_staffing'),
    (r'^leads/mission/(?P<mission_id>\d+)/deactivate$', 'deactivate_mission'),
    (r'^leads/consultant/(?P<consultant_id>\d+)/$', 'consultant_staffing'),
)

# Application prefix
pydici_prefix = r'^%s/' % pydici.settings.PYDICI_PREFIX
urlpatterns = patterns('', (pydici_prefix, include(pydici_patterns)))
