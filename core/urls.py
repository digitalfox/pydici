# -*- coding: UTF-8 -*-
"""URL dispatcher for core module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.urls import re_path
import core.views as v

core_urls = [ re_path(r'^$', v.index, name='index'),
              re_path(r'^search$', v.search, name='search'),
              re_path(r'^dashboard$', v.dashboard, name='dashboard'),
              re_path(r'^risks$', v.risk_reporting, name='risk_reporting'),
              re_path(r'^forbidden$', v.forbidden, name='forbidden'),
              re_path(r'^financial-control//?$', v.financial_control, name="financial_control"),
              re_path(r'^financial-control/(?P<start_date>\d{6})/?$', v.financial_control, name="financial_control"),
              re_path(r'^financial-control/(?P<start_date>\d{6})/(?P<end_date>\d{6})/?$', v.financial_control, name="financial_control")
            ]
