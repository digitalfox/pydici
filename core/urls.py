# -*- coding: UTF-8 -*-
"""URL dispatcher for core module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import patterns, url

core_urls = patterns('core.views',
                     url(r'^$', 'index', name='index'),
                     url(r'^search$', 'search', name='search'),
                     url(r'^dashboard$', 'dashboard', name='dashboard'),
                     url(r'^forbiden', 'forbiden', name='forbiden'),
                     url(r'^financial-control//?$', 'financialControl'),
                     url(r'^financial-control/(?P<start_date>\d{6})/?$', 'financialControl'),
                     url(r'^financial-control/(?P<start_date>\d{6})/(?P<end_date>\d{6})/?$', 'financialControl'),
                     )
