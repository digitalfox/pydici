# -*- coding: UTF-8 -*-
"""URL dispatcher for core module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import url
import core.views as v

core_urls = [url(r'^$', v.index, name='index'),
             url(r'^search$', v.search, name='search'),
             url(r'^dashboard$', v.dashboard, name='dashboard'),
             url(r'^risks$', v.risk_reporting, name='risk_reporting'),
             url(r'^forbiden$', v.forbiden, name='forbiden'),
             url(r'^financial-control//?$', v.financial_control, name="financial_control"),
             url(r'^financial-control/(?P<start_date>\d{6})/?$', v.financial_control, name="financial_control"),
             url(r'^financial-control/(?P<start_date>\d{6})/(?P<end_date>\d{6})/?$', v.financial_control, name="financial_control")
            ]
