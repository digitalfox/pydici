# -*- coding: UTF-8 -*-
"""URL dispatcher for core module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.urls import re_path
import core.views as v
import core.tables as t


core_urls = [ re_path(r'^$', v.index, name='index'),
              re_path(r'^search$', v.search, name='search'),
              re_path(r'^dashboard$', v.dashboard, name='dashboard'),
              re_path(r'^risks$', v.risk_reporting, name='risk_reporting'),
              re_path(r'^object_history/(?P<object_type>[a-z]+)/(?P<object_id>\d+)/$', v.object_history, name="object_history"),
              re_path(r'^tag/manage$', v.manage_tags, name="manage_tags"),
              re_path(r'^tag/(?P<tag_id>\d+)/$', v.tag, name="tag"),
              re_path(r'^forbidden$', v.forbidden, name='forbidden'),
              re_path(r'^financial-control//?$', v.financial_control, name="financial_control"),
              re_path(r'^financial-control/(?P<start_date>\d{6})/?$', v.financial_control, name="financial_control"),
              re_path(r'^financial-control/(?P<start_date>\d{6})/(?P<end_date>\d{6})/?$', v.financial_control, name="financial_control"),
              re_path(r'^datatable/all-tags/data/$', t.TagTableDT.as_view(), name='tag_table_DT'),
            ]
