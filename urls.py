# -*- coding: UTF-8 -*-
"""URL dispatcher
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
# Python import
import os

# Django import
from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template, redirect_to

admin.autodiscover()

# Config to get admin conctat
import pydici.settings
admin_contact = { "ADMINS" : pydici.settings.ADMINS }

# Feeds definition
from pydici.leads.feeds import LatestLeads, NewLeads, MyLatestLeads, WonLeads
from pydici.staffing.feeds import LatestStaffing, MyLatestStaffing

feeds = {
        "latest": LatestLeads,
        "new" :   NewLeads,
        "won" :   WonLeads,
        "mine":   MyLatestLeads,
        "latestStaffing" : LatestStaffing,
        "myLatestStaffing" : MyLatestStaffing
        }

# Models needed for generic views
from pydici.crm.models import ClientCompany

# Overide internal server error view
handler500 = "pydici.core.views.internal_error"

pydici_patterns = patterns('',
    # Admin
    (r'^admin/', include(admin.site.urls)),

    # Ajax select
    (r'^ajax_select/', include('ajax_select.urls')),
)

pydici_patterns += patterns('',
    # Direct to template and direct pages
    url(r'^forbiden', direct_to_template, {'template': 'forbiden.html', 'extra_context': admin_contact}, name='forbiden'),
    url(r'^help', redirect_to, {'url': pydici.settings.LEADS_HELP_PAGE}, name='help'),

    # Media
    (r'^media/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': os.path.join(pydici.settings.PYDICI_ROOTDIR, 'media')}),

    # Feeds
    url(r'^feeds/(?P<url>.*)/$', 'django.contrib.syndication.views.feed',
            {'feed_dict': feeds}, name='feed'),
)

# core module
pydici_patterns += patterns('pydici.core.views',
    url(r'^$', 'index', name='index'),
    url(r'^search$', 'search', name='search'),
    url(r'^mobile$', 'mobile_index', name='mobile_index'),
)

# Lead module
pydici_patterns += patterns('pydici.leads.views',
    (r'^leads/review', 'review'),
    (r'^leads/csv/(?P<target>.*)', 'csv_export'),
    (r'^leads/tag/(?P<tag_id>\d+)/$', 'tag'),
    (r'^leads/tags/(?P<lead_id>\d+)$', 'tags'),
    (r'^leads/tag/add$', 'add_tag'),
    (r'^leads/(?P<lead_id>\d+)/$', 'detail'),
    (r'^leads/sendmail/(?P<lead_id>\d+)/$', 'mail_lead'),
    url(r'^leads/mail/text', 'summary_mail', { "html" : False }, name="lead-mail-text"),
    url(r'^leads/mail/html', 'summary_mail', { "html" : True  }, name="lead-mail-html"),
    (r'^leads/graph/pie', 'graph_stat_pie'),
    (r'^leads/graph/bar', 'graph_stat_bar'),
)

# Staffing module
pydici_patterns += patterns('pydici.staffing.views',
    #url(r'^staffing/pdcreview/mobile$', 'pdc_review', { "mobile" : True }, name='m.pdcreview-index'),
    #url(r'^staffing/pdcreview/mobile/(?P<year>\d+)/(?P<month>\d+)/?$', 'pdc_review', { "mobile" : True }, name='m.pdcreview'),
    url(r'^staffing/pdcreview/?$', 'pdc_review', name='pdcreview-index'),
    url(r'^staffing/pdcreview/(?P<year>\d+)/(?P<month>\d+)/?$', 'pdc_review', name='pdcreview'),
    url(r'^staffing/mission/$', 'missions', name='missions'),
    url(r'^staffing/mission/all', 'missions', { 'onlyActive' : False }, 'all-missions'),
    (r'^staffing/mission/newfromdeal/(?P<lead_id>\d+)/$', 'create_new_mission_from_lead'),
    (r'^staffing/forecast/mission/(?P<mission_id>\d+)/$', 'mission_staffing'),
    (r'^staffing/mission/(?P<mission_id>\d+)/deactivate$', 'deactivate_mission'),
    (r'^staffing/forecast/consultant/(?P<consultant_id>\d+)/$', 'consultant_staffing'),
    (r'^staffing/timesheet/all/?$', 'all_timesheet'),
    (r'^staffing/timesheet/all/(?P<year>\d+)/(?P<month>\d+)/?$', 'all_timesheet'),
    (r'^staffing/timesheet/consultant/(?P<consultant_id>\d+)/$', 'consultant_timesheet'),
    (r'^staffing/timesheet/consultant/(?P<consultant_id>\d+)/(?P<year>\d+)/(?P<month>\d+)/?$', 'consultant_timesheet'),
    (r'^staffing/timesheet/consultant/(?P<consultant_id>\d+)/(?P<year>\d+)/(?P<month>\d+)/(?P<week>\d+)/?$', 'consultant_timesheet'),
    (r'^staffing/timesheet/mission/(?P<mission_id>\d+)/$', 'mission_timesheet'),
    (r'^staffing/rate/mission/(?P<mission_id>\d+)/consultant/(?P<consultant_id>\d+)/?$', 'mission_consultant_rate'),
    (r'^staffing/graph/rates/?$', 'graph_timesheet_rates_bar'),
    (r'^staffing/graph/rates/pie/consultant/(?P<consultant_id>\d+)', 'graph_consultant_rates_pie'),
    (r'^staffing/graph/rates/graph/consultant/(?P<consultant_id>\d+)', 'graph_consultant_rates_graph'),
)

# People module
pydici_patterns += patterns('pydici.people.views',
    (r'^people/consultant/(?P<consultant_id>\d+)/$', 'consultant_detail'),
)

# CRM module
pydici_patterns += patterns('pydici.crm.views',
    (r'^crm/company/(?P<company_id>\d+)/$', 'company_detail'),
)
pydici_patterns += patterns('',
            url(r'^crm/company/?$', 'django.views.generic.list_detail.object_list',
                                {'queryset': ClientCompany.objects.all(), }, 'clientcompany_list'),)

# Billing module
pydici_patterns += patterns('pydici.billing.views',
    (r'^billing/bill_review', 'bill_review'),
    (r'^billing/bill_delay', 'bill_payment_delay'),
    (r'^billing/bill/(?P<bill_id>\d+)/mark_bill_paid$', 'mark_bill_paid'),
    (r'^billing/bill/newfromdeal/(?P<lead_id>\d+)/$', 'create_new_bill_from_lead'),
    (r'^billing/graph/bar', 'graph_stat_bar'),
)

# Expense module
pydici_patterns += patterns('pydici.expense.views',
    (r'^expense/?$', 'expenses'),
    (r'^expense/(?P<expense_id>\d+)$', 'expenses'),
    (r'^expense/(?P<expense_id>\d+)/receipt$', 'expense_receipt'),
    (r'^expense/(?P<expense_id>\d+)/(?P<transition_id>\w+)', 'update_expense_state'),
    (r'^expense/history/?$', 'expenses_history'),
)

# Actionset module
pydici_patterns += patterns('pydici.actionset.views',
    (r'^actionset/?$', 'actionset_catalog'),
    (r'^actionset/(?P<action_state_id>\d+)/(?P<state>\w+)', 'update_action_state'),
)


# Application prefix
if pydici.settings.PYDICI_PREFIX:
    pydici_prefix = r'^%s/' % pydici.settings.PYDICI_PREFIX
else:
    pydici_prefix = ''

# Define URL patterns
urlpatterns = patterns('', (pydici_prefix, include(pydici_patterns)))
