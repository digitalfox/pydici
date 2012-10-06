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
from django.views.generic.simple import redirect_to

admin.autodiscover()

# Pydici settings
import pydici.settings

# Feeds definition
from pydici.leads.feeds import LatestLeads, NewLeads, MyLatestLeads, WonLeads
from pydici.staffing.feeds import LatestStaffing, MyLatestStaffing

feeds = {
        "latest": LatestLeads,
        "new": NewLeads,
        "won": WonLeads,
        "mine": MyLatestLeads,
        "latestStaffing": LatestStaffing,
        "myLatestStaffing": MyLatestStaffing
        }


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
    url(r'^dashboard$', 'dashboard', name='dashboard'),
    url(r'^forbiden', 'forbiden', name='forbiden'),
)

# Lead module
pydici_patterns += patterns('pydici.leads.views',
    (r'^leads/review', 'review'),
    (r'^leads/csv/(?P<target>.*)', 'csv_export'),
    (r'^leads/tag/(?P<tag_id>\d+)/$', 'tag'),
    (r'^leads/tags/(?P<lead_id>\d+)$', 'tags'),
    (r'^leads/tag/add$', 'add_tag'),
    (r'^leads/tag/remove/(?P<tag_id>\d+)/(?P<lead_id>\d+)$', 'remove_tag'),
    (r'^leads/(?P<lead_id>\d+)/$', 'detail'),
    (r'^leads/sendmail/(?P<lead_id>\d+)/$', 'mail_lead'),
    url(r'^leads/mail/text', 'summary_mail', {"html": False}, name="lead-mail-text"),
    url(r'^leads/mail/html', 'summary_mail', {"html": True}, name="lead-mail-html"),
    (r'^leads/graph/bar-jqp$', 'graph_bar_jqp'),
)

# Staffing module
pydici_patterns += patterns('pydici.staffing.views',
    url(r'^staffing/pdcreview/?$', 'pdc_review', name='pdcreview-index'),
    url(r'^staffing/pdcreview/(?P<year>\d+)/(?P<month>\d+)/?$', 'pdc_review', name='pdcreview'),
    url(r'^staffing/mission/$', 'missions', name='missions'),
    url(r'^staffing/mission/all', 'missions', {'onlyActive': False}, 'all-missions'),
    (r'^staffing/mission/(?P<mission_id>\d+)/$', 'mission_home'),
    (r'^staffing/mission/update/$', 'mission_update'),
    (r'^staffing/mission/newfromdeal/(?P<lead_id>\d+)/$', 'create_new_mission_from_lead'),
    (r'^staffing/forecast/mission/(?P<mission_id>\d+)/$', 'mission_staffing'),
    (r'^staffing/mission/(?P<mission_id>\d+)/deactivate$', 'deactivate_mission'),
    (r'^staffing/forecast/consultant/(?P<consultant_id>\d+)/$', 'consultant_staffing'),
    (r'^staffing/forecast/mass/$', 'mass_staffing'),
    (r'^staffing/timesheet/all/?$', 'all_timesheet'),
    (r'^staffing/timesheet/all/(?P<year>\d+)/(?P<month>\d+)/?$', 'all_timesheet'),
    (r'^staffing/timesheet/detailed/?$', 'detailed_csv_timesheet'),
    (r'^staffing/timesheet/detailed/(?P<year>\d+)/(?P<month>\d+)/?$', 'detailed_csv_timesheet'),
    (r'^staffing/timesheet/consultant/(?P<consultant_id>\d+)/$', 'consultant_timesheet'),
    (r'^staffing/timesheet/consultant/(?P<consultant_id>\d+)/(?P<year>\d+)/(?P<month>\d+)/?$', 'consultant_timesheet'),
    (r'^staffing/timesheet/consultant/(?P<consultant_id>\d+)/(?P<year>\d+)/(?P<month>\d+)/(?P<week>\d+)/?$', 'consultant_timesheet'),
    (r'^staffing/timesheet/mission/(?P<mission_id>\d+)/$', 'mission_timesheet'),
    (r'^staffing/contacts/mission/(?P<mission_id>\d+)/$', 'mission_contacts'),
    (r'^staffing/rate/?$', 'mission_consultant_rate'),
    (r'^staffing/graph/rates/?$', 'graph_timesheet_rates_bar'),
    (r'^staffing/graph/rates/graph-jqp/consultant/(?P<consultant_id>\d+)', 'graph_consultant_rates_jqp'),
)

# People module
pydici_patterns += patterns('pydici.people.views',
    (r'^people/home/consultant/(?P<consultant_id>\d+)/$', 'consultant_home'),
    (r'^people/detail/consultant/(?P<consultant_id>\d+)/$', 'consultant_detail'),
    (r'^people/detail/subcontractor/(?P<consultant_id>\d+)/$', 'subcontractor_detail'),
)

# CRM module
pydici_patterns += patterns('pydici.crm.views',
    (r'^crm/company/(?P<company_id>\d+)/$', 'company_detail'),
    (r'^crm/company/?$', 'company_list'),
    url(r'^crm/company/graph/sales$', 'graph_company_sales_jqp', name="graph_company_sales"),
    url(r'^crm/company/graph/sales/lastyear$', 'graph_company_sales_jqp', {"onlyLastYear": True}, name="graph_company_lastyear_sales"),
    url(r'^crm/company/(?P<company_id>\d+)/graph/business_activity$', 'graph_company_business_activity_jqp', name="graph_company_business_activity"),
)

# Billing module
pydici_patterns += patterns('pydici.billing.views',
    (r'^billing/bill_review', 'bill_review'),
    (r'^billing/bill_delay', 'bill_payment_delay'),
    (r'^billing/bill/(?P<bill_id>\d+)/mark_bill_paid$', 'mark_bill_paid'),
    (r'^billing/file/(?P<nature>.+)/(?P<bill_id>\d+)$', 'bill_file'),
    (r'^billing/pre_billing$', 'pre_billing'),
    (r'^billing/pre_billing/(?P<year>\d+)/(?P<month>\d+)/$', 'pre_billing'),
    (r'^billing/graph/bar', 'graph_stat_bar'),
)

# Expense module
pydici_patterns += patterns('pydici.expense.views',
    (r'^expense/?$', 'expenses'),
    (r'^expense/(?P<expense_id>\d+)$', 'expenses'),
    (r'^expense/(?P<expense_id>\d+)/receipt$', 'expense_receipt'),
    (r'^expense/(?P<expense_id>\d+)/(?P<transition_id>\w+)', 'update_expense_state'),
    (r'^expense/mission/(?P<mission_id>\d+)$', 'mission_expenses'),
    (r'^expense/history/(?P<year>\d+)?$', 'expenses_history'),
)

# Actionset module
pydici_patterns += patterns('pydici.actionset.views',
    (r'^actionset/?$', 'actionset_catalog'),
    (r'^actionset/(?P<action_state_id>\d+)/(?P<state>\w+)', 'update_action_state'),
    (r'^actionset/launch/(?P<actionset_id>\d+)', 'launch_actionset'),
)


# Application prefix
if pydici.settings.PYDICI_PREFIX:
    pydici_prefix = r'^%s/' % pydici.settings.PYDICI_PREFIX
else:
    pydici_prefix = ''

# Define URL patterns
urlpatterns = patterns('', (pydici_prefix, include(pydici_patterns)))
