# -*- coding: UTF-8 -*-
"""URL dispatcher for people module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import patterns, url


people_urls = patterns('people.views',
                       (r'^home/consultant/(?P<consultant_id>\d+)/$', 'consultant_home_by_id'),
                       (r'^home/consultant/(?P<consultant_trigramme>[a-zA-Z]{3})/$', 'consultant_home'),
                       (r'^detail/consultant/(?P<consultant_id>\d+)/$', 'consultant_detail'),
                       (r'^detail/subcontractor/(?P<consultant_id>\d+)/$', 'subcontractor_detail'),
                       (r'^similar_consultant/$', 'similar_consultant'),
                       )
