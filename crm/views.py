# coding: utf-8
"""
Pydici crm views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.template import RequestContext
from django.shortcuts import render_to_response

from pydici.crm.models import ClientCompany
from pydici.staffing.models import Timesheet
from pydici.leads.models import Lead

def company_detail(request, company_id):
    """Home page of client company"""

    company = ClientCompany.objects.get(id=company_id)

    # Find leads of this company
    leads = Lead.objects.filter(client__organisation__company=company)
    leads = leads.order_by("client", "state", "start_date")

    # Find consultant that work (=declare timesheet) for this company
    consultants = [ s.consultant for s in Timesheet.objects.filter(mission__lead__client__organisation__company=company)]
    consultants = list(set(consultants)) # Distinct


    return render_to_response("crm/clientcompany_detail.html",
                              {"company": company,
                               "leads": leads,
                               "consultants": consultants},
                               RequestContext(request))

