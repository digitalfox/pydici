# coding: utf-8
"""
Pydici people views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from django.shortcuts import render_to_response
from django.http import Http404
from django.template import RequestContext

from pydici.people.models import Consultant
from pydici.crm.models import ClientCompany

def consultant_detail(request, consultant_id):
    """Summary page of consultant activity"""
    try:
        consultant = Consultant.objects.get(id=consultant_id)
        staff = consultant.consultant_set.exclude(id=consultant.id)
        # Compute user current mission based on forecast
        missions = consultant.active_missions().filter(nature="PROD").filter(probability=100)
        companies = ClientCompany.objects.filter(clientorganisation__client__lead__mission__timesheet__consultant=consultant).distinct()
        leads_as_responsible = set(consultant.lead_responsible.active())
        leads_as_staffee = consultant.lead_set.active()
    except Consultant.DoesNotExist:
        raise Http404
    return render_to_response("people/consultant_detail.html",
                              {"consultant": consultant,
                               "staff" : staff,
                               "missions" : missions,
                               "companies": companies,
                               "leads_as_responsible" : leads_as_responsible,
                               "leads_as_staffee" : leads_as_staffee,
                               "user": request.user},
                               RequestContext(request))

