# coding: utf-8
"""
Pydici action set views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import json

from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.contrib.auth.decorators import permission_required, login_required
from django.utils.translation import ugettext as _
from django.core import urlresolvers
from django.template import RequestContext

from pydici.actionset.models import ActionSet, Action, ActionState

@login_required
def update_action_state(request, action_state_id, state):
    """Update action status.
    This view is designed to be called in ajax only
    @return: 0 on success, 1 on error/permission limitation"""
    error = HttpResponse(json.dumps({"error":True}), mimetype="application/json")
    try:
        actionState = ActionState.objects.get(id=action_state_id)
    except ActionState.DoesNotExist:
        return error
    if request.user == actionState.user and state in (i[0] for i in ActionState.ACTION_STATES):
        actionState.state = state
        actionState.save()
        return HttpResponse(json.dumps({"error":False, "id":action_state_id}), mimetype="application/json")
    else:
        return error

def actionset_catalog(request):
    """Catalog of all action set"""
    if request.user.has_perm("actionset.change_action") and request.user.has_perm("actionset.change_actionset"):
        can_change = True
    else:
        can_change = False
    return render_to_response("actionset/actionset_catalog.html",
                              {"actionsets": ActionSet.objects.all(),
                               "can_change" : can_change },
                               RequestContext(request))
