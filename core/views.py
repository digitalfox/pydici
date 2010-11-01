# coding: utf-8
"""
Pydici core views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

import pydici.settings

from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.db.models import Q

from pydici.leads.models import Lead
from pydici.people.models import Consultant, SalesMan
from pydici.crm.models import ClientCompany
from pydici.staffing.models import Mission

from pydici.core.forms import SearchForm


@login_required
def index(request):

    myLeadsAsResponsible = set()
    myLatestArchivedLeads = set()
    myLeadsAsStaffee = set()

    consultants = Consultant.objects.filter(trigramme__iexact=request.user.username)
    if consultants:
        consultant = consultants[0]
        myLeadsAsResponsible = set(consultant.lead_responsible.active())
        myLeadsAsStaffee = consultant.lead_set.active()
        myLatestArchivedLeads = set((consultant.lead_responsible.passive().order_by("-update_date")
                                  | consultant.lead_set.passive().order_by("-update_date"))[:10])

    salesmen = SalesMan.objects.filter(trigramme__iexact=request.user.username)
    if salesmen:
        salesman = salesmen[0]
        myLeadsAsResponsible.update(salesman.lead_set.active())
        myLatestArchivedLeads.update(salesman.lead_set.passive().order_by("-update_date")[:10])


    latestLeads = Lead.objects.all().order_by("-update_date")[:10]

    return render_to_response("core/index.html",
                              {"latest_leads": latestLeads,
                               "my_leads_as_responsible": myLeadsAsResponsible,
                               "my_leads_as_staffee": myLeadsAsStaffee,
                               "my_latest_archived_leads": myLatestArchivedLeads,
                               "user": request.user },
                               RequestContext(request))

@login_required
def search(request):
    """Very simple search function on all major pydici objects"""

    consultants = None
    clientCompanies = None
    leads = None
    missions = None

    words = request.GET.get("q", "")
    words = words.split()

    if words:
        # Consultant
        consultants = Consultant.objects.filter(active=True)
        for word in words:
            consultants = consultants.filter(Q(name__icontains=word) |
                                             Q(trigramme__icontains=word))

        # Client Company
        clientCompanies = ClientCompany.objects.all()
        for word in words:
            clientCompanies = clientCompanies.filter(name__icontains=word)

        # Leads
        leads = Lead.objects.all()
        for word in words:
            leads = leads.filter(Q(name__icontains=word) |
                                 Q(description__icontains=word))

        # Missions
        missions = Mission.objects.filter(active=True)
        for word in words:
            missions = missions.filter(description__icontains=word)

        # Add missions from lead
        missions = set(missions)
        for lead in leads:
            for mission in lead.mission_set.all():
                missions.add(mission)
        missions = list(missions)

    return render_to_response("core/search.html",
                              {"query" : " ".join(words),
                               "consultants": consultants,
                               "client_companies" : clientCompanies,
                               "leads" : leads,
                               "missions" : missions,
                               "user": request.user },
                               RequestContext(request))



