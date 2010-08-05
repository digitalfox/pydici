# coding: utf-8
"""
Pydici people views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from datetime import datetime

from django.shortcuts import render_to_response
from django.http import Http404
from django.template import RequestContext

from pydici.people.models import Consultant

def consultant_detail(request, consultant_id):
    """Summary page of consultant activity"""
    today = datetime.today()
    try:
        consultant = Consultant.objects.get(id=consultant_id)
        staff = consultant.consultant_set.exclude(id=consultant.id)
        # Compute user current mission
        current_staffing = consultant.staffing_set.filter(staffing_date__gte=today)
        current_missions = list(set(s.mission for s in current_staffing))
        current_companies = list(set([m.lead.client.organisation.company for m in current_missions if m.lead]))

        leads_as_responsible = set(consultant.lead_responsible.active())
        leads_as_staffee = consultant.lead_set.active()
    except Consultant.DoesNotExist:
        raise Http404
    return render_to_response("people/consultant_detail.html",
                              {"consultant": consultant,
                               "staff" : staff,
                               "current_missions" : current_missions,
                               "current_companies": current_companies,
                               "leads_as_responsible" : leads_as_responsible,
                               "leads_as_staffee" : leads_as_staffee,
                               "user": request.user},
                               RequestContext(request))

