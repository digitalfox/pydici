# coding: utf-8

import csv

from django.http import HttpResponse
from django.shortcuts import render_to_response

from pydici.leads.models import Lead
 
def index(request):
    latest_lead_list = Lead.objects.all().order_by("-update_date")[:5]
    return render_to_response("leads/index.html", {"latest_lead_list": latest_lead_list})

def detail(request, lead_id):
    try:
        lead=Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return HttpResponse("Lead %s does not exist." % lead_id)
    return HttpResponse("You're looking at lead %s." % lead.name)

def mail(request, html=True):
    """Ready to copy/paste in mail lead activity"""
    leads=Lead.objects.exclude(state__in=("LOST", "FORGIVEN", "WIN"))
    return render_to_response("leads/mail.html", {"leads": leads})

def csv_all(request):
    return csv_export(only_active=False)

def csv_active(request):
    return csv_export(only_active=True)

def csv_export(only_active=False):
    response = HttpResponse(mimetype="text/csv")
    response["Content-Disposition"] = "attachment; filename=plan-de-charge.csv"
    writer = csv.writer(response)
    writer.writerow(["Nom", "Client", "Description", "Suivi par", "Commercial", "Date de démarrage", "État",
                     "Échéance", "Staffing", "CA (k€)", "Création"])
    if only_active:
        leads=Lead.objects.exclude(state__in=("LOST", "FORGIVEN", "WIN"))
    else:
        leads=Lead.objects.all()
    for lead in leads.order_by("-update_date"):
        state=lead.get_state_display()
        row=[lead.name, lead.client, lead.description, lead.responsible, lead.salesman, lead.start_date, state,
                         lead.due_date, lead.staffing_list(), lead.sales, lead.update_date]
        row=[unicode(x).encode("UTF-8") for x in row]
        writer.writerow(row)
    return response
