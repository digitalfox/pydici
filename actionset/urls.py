# -*- coding: UTF-8 -*-
"""URL dispatcher for actionset module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import patterns, url


actionset_urls = patterns('actionset.views',
                          (r'^$', 'actionset_catalog'),
                          (r'^(?P<action_state_id>\d+)/(?P<state>\w+)', 'update_action_state'),
                          )
