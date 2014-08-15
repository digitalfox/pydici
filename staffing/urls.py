# -*- coding: UTF-8 -*-
"""URL dispatcher for staffing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import patterns, url

staffing_urls = patterns('staffing.views',
                         url(r'^pdcreview/?$', 'pdc_review', name='pdcreview-index'),
                         url(r'^pdcreview/(?P<year>\d+)/(?P<month>\d+)/?$', 'pdc_review', name='pdcreview'),
                         url(r'^mission/$', 'missions', name='missions'),
                         url(r'^mission/all', 'missions', {'onlyActive': False}, 'all-missions'),
                         (r'^mission/(?P<mission_id>\d+)/$', 'mission_home'),
                         (r'^mission/update/$', 'mission_update'),
                         (r'^mission/newfromdeal/(?P<lead_id>\d+)/$', 'create_new_mission_from_lead'),
                         (r'^forecast/mission/(?P<mission_id>\d+)/$', 'mission_staffing'),
                         (r'^mission/(?P<mission_id>\d+)/deactivate$', 'deactivate_mission'),
                         (r'^forecast/consultant/(?P<consultant_id>\d+)/$', 'consultant_staffing'),
                         (r'^forecast/mass/$', 'mass_staffing'),
                         (r'^timesheet/all/?$', 'all_timesheet'),
                         (r'^timesheet/all/(?P<year>\d+)/(?P<month>\d+)/?$', 'all_timesheet'),
                         (r'^timesheet/detailed/?$', 'detailed_csv_timesheet'),
                         (r'^timesheet/detailed/(?P<year>\d+)/(?P<month>\d+)/?$', 'detailed_csv_timesheet'),
                         (r'^timesheet/consultant/(?P<consultant_id>\d+)/$', 'consultant_timesheet'),
                         (r'^timesheet/consultant/(?P<consultant_id>\d+)/(?P<year>\d+)/(?P<month>\d+)/?$', 'consultant_timesheet'),
                         (r'^timesheet/consultant/(?P<consultant_id>\d+)/(?P<year>\d+)/(?P<month>\d+)/(?P<week>\d+)/?$', 'consultant_timesheet'),
                         (r'^timesheet/mission/(?P<mission_id>\d+)/$', 'mission_timesheet'),
                         (r'^holidays_planning/?$', 'holidays_planning'),
                         (r'^holidays_planning/(?P<year>\d+)/(?P<month>\d+)/?$', 'holidays_planning'),
                         (r'^contacts/mission/(?P<mission_id>\d+)/$', 'mission_contacts'),
                         (r'^rate/?$', 'mission_consultant_rate'),
                         (r'^pdc-detail/(?P<consultant_id>\d+)/(?P<staffing_date>\d+)/?$', 'pdc_detail'),
                         (r'^graph/timesheet-rates/?$', 'graph_timesheet_rates_bar_jqp'),
                         (r'^graph/profile-rates/?$', 'graph_profile_rates_jqp'),
                         (r'^graph/rates/consultant/(?P<consultant_id>\d+)', 'graph_consultant_rates_jqp'),
                         )
