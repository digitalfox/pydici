# coding: utf-8
"""
Pydici crm views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from django.template import RequestContext
from django.shortcuts import render_to_response

from pydici.crm.models import ClientCompany
from pydici.staffing.models import Mission, Timesheet

def company_detail(request, company_id):
    """Home page of client company"""

    company = ClientCompany.objects.get(id=company_id)

    # Find missions of this company
    missions = Mission.objects.filter(lead__client__organisation__company=company)
    missions = missions.order_by("lead__client").order_by("lead__state").order_by("lead__start_date")

    # Find consultant that work (=declare timesheet) for this company
    consultants = [ s.consultant for s in Timesheet.objects.filter(mission__lead__client__organisation__company=company)]
    consultants = list(set(consultants)) # Distinct


    return render_to_response("crm/clientcompany_detail.html",
                              {"company": company,
                               "missions": missions,
                               "consultants": consultants},
                               RequestContext(request))

