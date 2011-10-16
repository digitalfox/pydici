# coding: utf-8
"""
Pydici crm views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.template import RequestContext
from django.shortcuts import render_to_response

from pydici.crm.models import ClientCompany, Client
from pydici.staffing.models import Timesheet
from pydici.leads.models import Lead
from pydici.core.decorator import pydici_non_public

@pydici_non_public
def company_detail(request, company_id):
    """Home page of client company"""

    company = ClientCompany.objects.get(id=company_id)

    # Find leads of this company
    leads = Lead.objects.filter(client__organisation__company=company).select_related()
    leads = leads.order_by("client", "state", "start_date")

    # Find consultant that work (=declare timesheet) for this company
    consultants = [ s.consultant for s in Timesheet.objects.filter(mission__lead__client__organisation__company=company).select_related()]
    consultants = list(set(consultants)) # Distinct


    return render_to_response("crm/clientcompany_detail.html",
                              {"company": company,
                               "leads": leads,
                               "consultants": consultants,
                               "clients": Client.objects.filter(organisation__company=company)},
                               RequestContext(request))

@pydici_non_public
def company_list(request):
    """Client company list"""
    return render_to_response("crm/clientcompany_list.html",
                              {"companies": ClientCompany.objects.all() },
                               RequestContext(request))

