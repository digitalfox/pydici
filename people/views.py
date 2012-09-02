# coding: utf-8
"""
Pydici people views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.shortcuts import render_to_response
from django.http import Http404, HttpResponseRedirect
from django.core import urlresolvers
from django.template import RequestContext

from pydici.people.models import Consultant
from pydici.crm.models import Company
from pydici.core.decorator import pydici_non_public


@pydici_non_public
def consultant_detail(request, consultant_id):
    """Summary page of consultant activity"""
    try:
        consultant = Consultant.objects.get(id=consultant_id)
        staff = consultant.team()
        # Compute user current mission based on forecast
        missions = consultant.active_missions().filter(nature="PROD").filter(probability=100)
        companies = Company.objects.filter(clientorganisation__client__lead__mission__timesheet__consultant=consultant).distinct()
        business_territory = Company.objects.filter(businessOwner=consultant)
        leads_as_responsible = set(consultant.lead_responsible.active())
        leads_as_staffee = consultant.lead_set.active()
    except Consultant.DoesNotExist:
        raise Http404
    return render_to_response("people/consultant_detail.html",
                              {"consultant": consultant,
                               "staff": staff,
                               "missions": missions,
                               "companies": companies,
                               "business_territory": business_territory,
                               "leads_as_responsible": leads_as_responsible,
                               "leads_as_staffee": leads_as_staffee,
                               "user": request.user},
                               RequestContext(request))


def subcontractor_detail(request, consultant_id):
    """This is the subcontractor home page"""
    try:
        consultant = Consultant.objects.get(id=consultant_id)
        missions = consultant.active_missions().filter(nature="PROD").filter(probability=100)
        companies = Company.objects.filter(clientorganisation__client__lead__mission__timesheet__consultant=consultant).distinct()
        leads_as_staffee = consultant.lead_set.active()
    except Consultant.DoesNotExist:
        raise Http404
    if not consultant.subcontractor:
        raise Http404
    return render_to_response("people/subcontractor_detail.html",
                              {"consultant": consultant,
                               "missions": missions,
                               "companies": companies,
                               "leads_as_staffee": leads_as_staffee,
                               "user": request.user},
                               RequestContext(request))
