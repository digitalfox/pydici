# -*- coding: UTF-8 -*-
"""URL dispatcher
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
# Python import
import os

# Django import
from django.conf.urls import include
from django.urls import re_path
from django.conf import settings
from django.contrib import admin
from django.views.generic.base import RedirectView
import django.views.static

admin.autodiscover()

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

from core.views import PydiciSelect2View, PydiciSelect2SubcontractorView

pydici_patterns = [re_path(r'^admin/', admin.site.urls), ]

# Help page
try:
    help_page_url = get_parameter("HELP_PAGE")
except:
    # Corner case, during initial migration Parameter table does not exist yet
    help_page_url = ""

if settings.DEBUG:
    import debug_toolbar
    pydici_patterns.append( re_path(r'^__debug__/', include(debug_toolbar.urls)))

pydici_patterns.extend([
    # Direct to template and direct pages
    re_path(r'^help', RedirectView.as_view(url=help_page_url, permanent=True), name='help'),

    # Media
    re_path(r'^media/(?P<path>.*)$', django.views.static.serve,
            {'document_root': os.path.join(settings.PYDICI_ROOTDIR, 'media')}),

    # Feeds
    re_path(r'^feeds/latest/?$', LatestLeads(), name='latest'),
    re_path(r'^feeds/new/?$', NewLeads(), name='new'),
    re_path(r'^feeds/won/?$', WonLeads(), name='won'),
    re_path(r'^feeds/mine/?$', MyLatestLeads(), name='mine'),
    re_path(r'^feeds/latestStaffing/?$', LatestStaffing(), name='latestStaffing'),
    re_path(r'^feeds/myLatestStaffing/?$', MyLatestStaffing(), name='myLatestStaffing'),
    re_path(r'^feeds/archivedMission/?$', ArchivedMission(), name='archivedMission'),
    ])

# Add select2 url
pydici_patterns.append(re_path(r"^select2/auto.json$", PydiciSelect2View.as_view(), name="pydici-select2-view"))
pydici_patterns.append(re_path(r"^select2/subcontractor/auto.json$", PydiciSelect2SubcontractorView.as_view(), name="pydici-select2-view-subcontractor"))


# Include pydici modules URLs
pydici_patterns.extend([re_path("", include((core_urls, "core"), namespace="core")),
                        re_path("people/", include((people_urls, "people"), namespace="people")),
                        re_path("crm/", include((crm_urls, "crm"), namespace="crm")),
                        re_path("staffing/", include((staffing_urls, "staffing"), namespace="staffing")),
                        re_path("billing/", include((billing_urls, "billing"), namespace="billing")),
                        re_path("actionset/", include((actionset_urls, "actionset"), namespace="actionset")),
                        re_path("expense/", include((expense_urls, "expense"), namespace="expense")),
                        re_path("leads/", include((leads_urls, "lead"), namespace="leads"))
                        ])


# Define URL patterns
urlpatterns = [re_path("", include(pydici_patterns))]
