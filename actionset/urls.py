# -*- coding: UTF-8 -*-
"""URL dispatcher for actionset module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls  import re_path
import actionset.views as v

actionset_urls = [ re_path(r'^$', v.actionset_catalog, name="actionset_catalog"),
                   re_path(r'^(?P<action_state_id>\d+)/(?P<state>\w+)$', v.update_action_state, name="update_action_state"),
                  ]
