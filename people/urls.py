# -*- coding: UTF-8 -*-
"""URL dispatcher for people module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import url
import people.views as v


people_urls = [url(r'^home/consultant/(?P<consultant_id>\d+)/$', v.consultant_home_by_id),
               url(r'^home/consultant/(?P<consultant_trigramme>[a-zA-Z]{3})/$', v.consultant_home),
               url(r'^detail/consultant/(?P<consultant_id>\d+)/$', v.consultant_detail),
               url(r'^detail/subcontractor/(?P<consultant_id>\d+)/$', v.subcontractor_detail),
               ]
