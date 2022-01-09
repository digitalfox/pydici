# -*- coding: UTF-8 -*-
"""URL dispatcher for people module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls  import re_path
import people.views as v


people_urls = [ re_path(r'^home/consultant/(?P<consultant_id>\d+)/$', v.consultant_home_by_id, name="consultant_home_by_id"),
                re_path(r'^home/consultant/(?P<consultant_trigramme>[a-zA-Z]{3})/$', v.consultant_home, name="consultant_home"),
                re_path(r'^detail/consultant/(?P<consultant_id>\d+)/$', v.consultant_detail, name="consultant_detail"),
                re_path(r'^detail/subcontractor/(?P<consultant_id>\d+)/$', v.subcontractor_detail, name="subcontractor_detail"),
                re_path(r'^consultant_list$', v.consultant_list, name="consultant_list"),
                re_path(r'^consultant_provisioning$', v.consultant_provisioning, name="consultant_provisioning"),
                re_path(r'^consultant_deactivation$', v.consultant_deactivation, name="consultant_deactivation"),
                re_path(r'^graph/people-count/?$', v.graph_people_count, name="graph_people_count"),
               ]
