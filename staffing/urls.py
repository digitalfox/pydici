# -*- coding: UTF-8 -*-
"""URL dispatcher for staffing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import patterns, url
import staffing.views as v
import staffing.tables as t

staffing_urls = patterns('staffing.views',
                         url(r'^pdcreview/?$', 'pdc_review', name='pdcreview-index'),
                         url(r'^pdcreview/(?P<year>\d+)/(?P<month>\d+)/?$', 'pdc_review', name='pdcreview'),
                         url(r'^production-report/?$', 'prod_report', name='prodreport-index'),
                         url(r'^production-report/(?P<year>\d+)/(?P<month>\d+)/?$', 'prod_report', name='prodreport'),
                         url(r'^mission/$', 'missions', name='missions'),
                         url(r'^mission/all', 'missions', {'onlyActive': False}, 'all-missions'),
                         (r'^mission/(?P<mission_id>\d+)/$', 'mission_home'),
                         url(r'^mission/update/$', 'mission_update', name="mission_inline_update"),
                         url(r'^mission/(?P<pk>\d+)/update$', v.MissionUpdate.as_view(), name='mission_update'),
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
                         url(r'^datatable/all-missions/data/$', t.MissionsTableDT.as_view(), name='all_mission_table_DT'),
                         url(r'^datatable/active-missions/data/$', t.ActiveMissionsTableDT.as_view(), name='active_mission_table_DT'),
                         (r'^graph/timesheet-rates/?$', 'graph_timesheet_rates_bar_jqp'),
                         (r'^graph/timesheet-rates/subsidiary/(?P<subsidiary_id>\d+)$', 'graph_timesheet_rates_bar_jqp'),
                         (r'^graph/timesheet-rates/team/(?P<team_id>\d+)$', 'graph_timesheet_rates_bar_jqp'),
                         (r'^graph/profile-rates/?$', 'graph_profile_rates_jqp'),
                         (r'^graph/profile-rates/subsidiary/(?P<subsidiary_id>\d+)$', 'graph_profile_rates_jqp'),
                         (r'^graph/profile-rates/team/(?P<team_id>\d+)$', 'graph_profile_rates_jqp'),
                         (r'^graph/rates/consultant/(?P<consultant_id>\d+)', 'graph_consultant_rates'),
                         )
