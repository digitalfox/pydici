# coding: utf-8
"""
Pydici crm views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import json
from datetime import date, timedelta

from django.template import RequestContext
from django.shortcuts import render_to_response
from django.db.models import Sum, Min
from django.views.decorators.cache import cache_page

from pydici.crm.models import Company, Client, Contact, AdministrativeContact
from pydici.staffing.models import Timesheet
from pydici.leads.models import Lead
from pydici.core.decorator import pydici_non_public
from pydici.core.utils import COLORS
from pydici.billing.models import ClientBill


@pydici_non_public
def company_detail(request, company_id):
    """Home page of client company"""

    company = Company.objects.get(id=company_id)

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
                               "business_contacts": Contact.objects.filter(client__organisation__company=company).distinct(),
                               "mission_contacts": Contact.objects.filter(missioncontact__company=company).distinct(),
                               "administrative_contacts": AdministrativeContact.objects.filter(company=company),
                               "clients": Client.objects.filter(organisation__company=company),
                               "companies": Company.objects.all()},
                               RequestContext(request))


@pydici_non_public
def company_list(request):
    """Client company list"""
    companies = set()
    for client in Client.objects.all():
        companies.add(client.organisation.company)
    return render_to_response("crm/clientcompany_list.html",
                              {"companies": list(companies)},
                               RequestContext(request))


@pydici_non_public
@cache_page(60 * 60 * 24)
def graph_company_sales_jqp(request, onlyLastYear=False):
    """Sales repartition per company"""
    graph_data = []
    labels = []
    minDate = ClientBill.objects.aggregate(Min("creation_date")).values()[0]
    if onlyLastYear:
        data = ClientBill.objects.filter(creation_date__gt=(date.today() - timedelta(365)))
    else:
        data = ClientBill.objects.all()
    data = data.values("lead__client__organisation__company__name")
    data = data.order_by("lead__client__organisation__company").annotate(Sum("amount"))
    data = data.order_by("amount__sum").reverse()[0:9]
    for i in data:
        graph_data.append((i["lead__client__organisation__company__name"], float(i["amount__sum"])))
    total = sum([i[1] for i in graph_data])
    for company, amount in graph_data:
        labels.append(u"%d k€ (%d%%)" % (amount / 1000, 100 * amount / total))

    return render_to_response("crm/graph_company_sales_jqp.html",
                              {"graph_data": json.dumps([graph_data]),
                               "series_colors": COLORS,
                               "only_last_year": onlyLastYear,
                               "min_date": minDate,
                               "labels": json.dumps(labels),
                               "user": request.user},
                               RequestContext(request))
