# -*- coding: UTF-8 -*-
"""URL dispatcher
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
# Python import
import os

# Django import
from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.views.generic.base import RedirectView

admin.autodiscover()

# Pydici settings
import pydici.settings
from core.utils import get_parameter

# Feeds definition
from leads.feeds import LatestLeads, NewLeads, MyLatestLeads, WonLeads
from staffing.feeds import LatestStaffing, MyLatestStaffing, ArchivedMission

# URLs from pydici modules
from crm.urls import crm_urls
from people.urls import people_urls
from staffing.urls import staffing_urls
from billing.urls import billing_urls
from actionset.urls import actionset_urls
from expense.urls import expense_urls
from leads.urls import leads_urls
from core.urls import core_urls
from batch.incwo.urls import incwo_urls


# Overide internal server error view
handler500 = "core.views.internal_error"

pydici_patterns = patterns('', (r'^admin/', include(admin.site.urls)))

if pydici.settings.DEBUG:
    import debug_toolbar
    pydici_patterns += patterns('', url(r'^__debug__/', include(debug_toolbar.urls)),)

pydici_patterns += patterns('',
    # Direct to template and direct pages
    url(r'^help', RedirectView.as_view(url=get_parameter("HELP_PAGE"), permanent=True), name='help'),

    # Media
    (r'^media/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': os.path.join(pydici.settings.PYDICI_ROOTDIR, 'media')}),

    # Feeds
    url(r'^feeds/latest/?$', LatestLeads(), name='latest'),
    url(r'^feeds/new/?$', NewLeads(), name='new'),
    url(r'^feeds/won/?$', WonLeads(), name='won'),
    url(r'^feeds/mine/?$', MyLatestLeads(), name='mine'),
    url(r'^feeds/latestStaffing/?$', LatestStaffing(), name='latestStaffing'),
    url(r'^feeds/myLatestStaffing/?$', MyLatestStaffing(), name='myLatestStaffing'),
    url(r'^feeds/archivedMission/?$', ArchivedMission(), name='archivedMission'),
)


# Include pydici modules URLs
pydici_patterns += patterns("",
                            ("", include(core_urls)),
                            ("people/", include(people_urls)),
                            ("crm/", include(crm_urls)),
                            ("staffing/", include(staffing_urls)),
                            ("billing/", include(billing_urls)),
                            ("actionset/", include(actionset_urls)),
                            ("expense/", include(expense_urls)),
                            ("leads/", include(leads_urls)),
                            ("incwo/", include(incwo_urls)),
                            )


# Application prefix
if pydici.settings.PYDICI_PREFIX:
    pydici_prefix = r'^%s/' % pydici.settings.PYDICI_PREFIX
else:
    pydici_prefix = ''

# Define URL patterns
urlpatterns = patterns('', (pydici_prefix, include(pydici_patterns)))
