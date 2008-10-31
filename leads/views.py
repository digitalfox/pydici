# coding: utf-8

import csv

import pydici.settings

from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required

from pydici.leads.models import Lead, Consultant
from pydici.leads.utils import send_lead_mail

@login_required
def index(request):
    consultants=Consultant.objects.filter(trigramme__iexact=request.user.username)
    print consultants
    if consultants:
        consultant=consultants[0]
        myLeadsAsResponsible=consultant.lead_responsible.active()
        myLeadsAsStaffee=consultant.lead_set.active()
    else:
        myLeadsAsResponsible=None
        myLeadsAsStaffee=None

    latestLeads=Lead.objects.all().order_by("-update_date")[:10]

    return render_to_response("leads/index.html", {"latest_leads": latestLeads,
                                                   "my_leads_as_responsible": myLeadsAsResponsible,
                                                   "my_leads_as_staffee": myLeadsAsStaffee })

def summary_mail(request, html=True):
    """Ready to copy/paste in mail summary leads activity"""
    leads=Lead.objects.active()
    if html:
        return render_to_response("leads/mail.html", {"leads": leads})
    else:
        return render_to_response("leads/mail.txt", {"leads": leads}, mimetype="text/plain")

def detail(request, lead_id):
    """Ready to copy/paste in mail a lead description"""
    try:
        lead=Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return HttpResponse("Lead %s does not exist." % lead_id)
    return render_to_response("leads/lead_mail.html", {"lead": lead, "link_root": pydici.settings.LEADS_MAIL_LINK_ROOT})

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
        return HttpResponse("Lead %s does not exist." % lead_id)
    try:
        send_lead_mail(lead)
        return HttpResponse("Lead %s was sent to %s !" % (lead_id, pydici.settings.LEADS_MAIL_TO))
    except Exception, e:
        return HttpResponse("Failed to send mail: %s" % e)
