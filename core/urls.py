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
             url(r'^risks$', v.riskReporting, name='risks'),
             url(r'^forbiden', v.forbiden, name='forbiden'),
             url(r'^financial-control//?$', v.financialControl),
             url(r'^financial-control/(?P<start_date>\d{6})/?$', v.financialControl),
             url(r'^financial-control/(?P<start_date>\d{6})/(?P<end_date>\d{6})/?$', v.financialControl),
             url(r"^select2/auto.json$", v.PydiciSelect2View.as_view(), name="django_select2-json"),
            ]
