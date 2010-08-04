# coding: utf-8
"""
Pydici crm views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from django.template import RequestContext
from django.shortcuts import render_to_response

from pydici.crm.models import ClientCompany
from pydici.staffing.models import Mission

def company_detail(request, company_id):
    """Home page of client company"""

    company = ClientCompany.objects.get(id=company_id)

    missions = Mission.objects.filter(lead__client__organisation__company=company)
    missions = missions.order_by("lead__client").order_by("lead__state").order_by("lead__start_date")


    return render_to_response("crm/company_detail.html",
                              {"company": company,
                               "missions": missions},
                               RequestContext(request))






