# coding: utf-8
"""
Pydici crm views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import json
from datetime import date, timedelta

from django.shortcuts import render
from django.db.models import Sum, Min
from django.views.decorators.cache import cache_page
from django.utils.translation import ugettext as _

from crm.models import Company, Client, Contact, AdministrativeContact
from staffing.models import Timesheet
from leads.models import Lead
from core.decorator import pydici_non_public
from core.utils import sortedValues, previousMonth, COLORS
from billing.models import ClientBill


@pydici_non_public
def company_detail(request, company_id):
    """Home page of client company"""

    company = Company.objects.get(id=company_id)

    # Find leads of this company
    leads = Lead.objects.filter(client__organisation__company=company).select_related()
    leads = leads.order_by("client", "state", "start_date")

    # Find consultant that work (=declare timesheet) for this company
    consultants = [s.consultant for s in Timesheet.objects.filter(mission__lead__client__organisation__company=company).select_related()]
    consultants = list(set(consultants))  # Distinct

    companies = Company.objects.filter(clientorganisation__client__id__isnull=False).distinct()

    return render(request, "crm/clientcompany_detail.html",
                  {"company": company,
                   "leads": leads,
                   "consultants": consultants,
                   "business_contacts": Contact.objects.filter(client__organisation__company=company).distinct(),
                   "mission_contacts": Contact.objects.filter(missioncontact__company=company).distinct(),
                   "administrative_contacts": AdministrativeContact.objects.filter(company=company),
                   "clients": Client.objects.filter(organisation__company=company),
                   "companies": companies})


@pydici_non_public
def company_list(request):
    """Client company list"""
    companies = Company.objects.filter(clientorganisation__client__id__isnull=False).distinct()
    return render(request, "crm/clientcompany_list.html",
                  {"companies": list(companies)})


@pydici_non_public
@cache_page(60 * 60 * 24)
def graph_company_sales_jqp(request, onlyLastYear=False):
    """Sales repartition per company"""
    graph_data = []
    labels = []
    small_clients_amount = 0
    minDate = ClientBill.objects.aggregate(Min("creation_date")).values()[0]
    if onlyLastYear:
        data = ClientBill.objects.filter(creation_date__gt=(date.today() - timedelta(365)))
    else:
        data = ClientBill.objects.all()
    data = data.values("lead__client__organisation__company__name")
    data = data.order_by("lead__client__organisation__company").annotate(Sum("amount"))
    data = data.order_by("amount__sum").reverse()
    small_clients = data[8:]
    for i in small_clients:
        small_clients_amount += float(i["amount__sum"])
    data = data[0:8]
    for i in data:
        graph_data.append((i["lead__client__organisation__company__name"], float(i["amount__sum"])))
    graph_data.append((_("Others"), small_clients_amount))
    total = sum([i[1] for i in graph_data])
    for company, amount in graph_data:
        labels.append(u"%d k€ (%d%%)" % (amount / 1000, 100 * amount / total))

    return render(request, "crm/graph_company_sales_jqp.html",
                  {"graph_data": json.dumps([graph_data]),
                   "series_colors": COLORS,
                   "only_last_year": onlyLastYear,
                   "min_date": minDate,
                   "labels": json.dumps(labels),
                   "user": request.user})


@pydici_non_public
@cache_page(60 * 60)
def graph_company_business_activity_jqp(request, company_id):
    """Business activity (leads and bills) for a company
    @todo: extend this graph to multiple companies"""
    graph_data = []
    billsData = dict()
    allLeadsData = dict()
    wonLeadsData = dict()
    minDate = date.today()
    company = Company.objects.get(id=company_id)

    for bill in ClientBill.objects.filter(lead__client__organisation__company=company):
        kdate = bill.creation_date.replace(day=1)
        if kdate in billsData:
            billsData[kdate] += int(float(bill.amount) / 1000)
        else:
            billsData[kdate] = int(float(bill.amount) / 1000)

    for lead in Lead.objects.filter(client__organisation__company=company):
        kdate = lead.creation_date.date().replace(day=1)
        if lead.state == "WON":
            datas = (allLeadsData, wonLeadsData)
        else:
            datas = (allLeadsData,)
        for data in datas:
            if kdate in data:
                data[kdate] += 1
            else:
                data[kdate] = 1

    for data in (billsData, allLeadsData, wonLeadsData):
        kdates = data.keys()
        kdates.sort()
        isoKdates = [a.isoformat() for a in kdates]  # List of date as string in ISO format
        if len(kdates) > 0 and kdates[0] < minDate:
            minDate = kdates[0]
        data = zip(isoKdates, sortedValues(data))
        if not data:
            data = ((0, 0))
        graph_data.append(data)

    minDate = previousMonth(minDate)

    return render(request, "crm/graph_company_business_activity_jqp.html",
                  {"graph_data": json.dumps(graph_data),
                   "series_colors": COLORS,
                   "min_date": minDate.isoformat(),
                   "user": request.user})
