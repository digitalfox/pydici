# coding: utf-8
"""
Pydici core views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from datetime import datetime, timedelta, date
import os


from ajax_select.fields import AutoCompleteSelectField

import pydici.settings

from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required, permission_required
from django.db import connection
from django.utils.translation import ugettext as _

from pydici.leads.models import Lead

from pydici.people.models import Consultant, SalesMan
from pydici.staffing.models import Staffing, Mission, Holiday

from pydici.core.utils import send_lead_mail, to_int_or_round


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

    return render_to_response("leads/index.html", {"latest_leads": latestLeads,
                                                   "my_leads_as_responsible": myLeadsAsResponsible,
                                                   "my_leads_as_staffee": myLeadsAsStaffee,
                                                   "my_latest_archived_leads": myLatestArchivedLeads,
                                                   "user": request.user })

