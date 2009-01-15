# coding: utf-8
"""
Django views. All http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: BSD
"""
import csv
from datetime import datetime, timedelta

import pydici.settings

from django.http import HttpResponse, Http404
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django.contrib.admin.models import LogEntry
from django.db.models import Q

from pydici.leads.models import Lead, Consultant, SalesMan
from pydici.leads.utils import send_lead_mail

@login_required
def index(request):

    myLeadsAsResponsible=set()
    myLatestArchivedLeads=set()
    myLeadsAsStaffee=set()

    consultants=Consultant.objects.filter(trigramme__iexact=request.user.username)
    if consultants:
        consultant=consultants[0]
        myLeadsAsResponsible=set(consultant.lead_responsible.active())
        myLeadsAsStaffee=consultant.lead_set.active()
        myLatestArchivedLeads=set(consultant.lead_responsible.passive().order_by("-update_date")[:5])

    salesmen=SalesMan.objects.filter(trigramme__iexact=request.user.username)
    if salesmen:
        salesman=salesmen[0]
        myLeadsAsResponsible.update(salesman.lead_set.active())
        myLatestArchivedLeads.update(salesman.lead_set.passive().order_by("-update_date")[:5])


    latestLeads=Lead.objects.all().order_by("-update_date")[:10]

    return render_to_response("leads/index.html", {"latest_leads": latestLeads,
                                                   "my_leads_as_responsible": myLeadsAsResponsible,
                                                   "my_leads_as_staffee": myLeadsAsStaffee,
                                                   "my_latest_archived_leads": myLatestArchivedLeads,
                                                   "user": request.user })

def summary_mail(request, html=True):
    """Ready to copy/paste in mail summary leads activity"""
    today=datetime.today()
    delay=timedelta(days=10) #(10 days)

    active_leads=Lead.objects.active().order_by("state", "-update_date")
    passive_leads=Lead.objects.passive().filter(update_date__gte=(today-delay)).order_by("state", "-update_date")
    if html:
        return render_to_response("leads/mail.html", {"lead_group": [active_leads, passive_leads] })
    else:
        return render_to_response("leads/mail.txt", {"lead_group": [active_leads, passive_leads] },
                                  mimetype="text/plain; charset=utf-8")

@login_required
def detail(request, lead_id):
    """Lead detailed description"""
    try:
        lead=Lead.objects.get(id=lead_id)
        actionList = LogEntry.objects.filter(object_id = lead_id,
                                              content_type__name="lead")
        actionList=actionList.select_related().order_by('action_time')
    except Lead.DoesNotExist:
        raise Http404
    return render_to_response("leads/lead_detail.html", {"lead": lead,
                                                         "link_root": pydici.settings.LEADS_MAIL_LINK_ROOT,
                                                         "action_list": actionList,
                                                         "user": request.user})

def csv_export(request, target):
    response = HttpResponse(mimetype="text/csv")
    response["Content-Disposition"] = "attachment; filename=plan-de-charge.csv"
    writer = csv.writer(response)
    writer.writerow(["Nom", "Client", "Description", "Suivi par", "Commercial", "Date de démarrage", "État",
                     "Échéance", "Staffing", "CA (k€)", "Code A6", "Création", "Mise à jour"])
    if target!="all":
        leads=Lead.objects.active()
    else:
        leads=Lead.objects.all()
    for lead in leads.order_by("-update_date"):
        state=lead.get_state_display()
        row=[lead.name, lead.client, lead.description, lead.responsible, lead.salesman, lead.start_date, state,
                         lead.due_date, lead.staffing_list(), lead.sales, lead.salesId, lead.creation_date, lead.update_date]
        row=[unicode(x).encode("UTF-8") for x in row]
        writer.writerow(row)
    return response

def mail_lead(request, lead_id=0):
    try:
        lead=Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        raise Http404
    try:
        send_lead_mail(lead)
        return HttpResponse("Lead %s was sent to %s !" % (lead_id, pydici.settings.LEADS_MAIL_TO))
    except Exception, e:
        return HttpResponse("Failed to send mail: %s" % e)

def review(request):
    today=datetime.today()
    delay=timedelta(days=10) #(10 days)
    recentArchivedLeads=Lead.objects.passive().filter(Q(update_date__gte=(today-delay)) |
                                                      Q(state="WIN", salesId="") |
                                                      Q(state="SLEEPING"))
    recentArchivedLeads=recentArchivedLeads.order_by("state", "-update_date")
    return render_to_response("leads/review.html", {"recent_archived_leads" : recentArchivedLeads,
                                                    "active_leads" : Lead.objects.active(),
                                                    "user": request.user })