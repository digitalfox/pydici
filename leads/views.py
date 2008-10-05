# coding: utf-8

import csv

from django.http import HttpResponse
from django.shortcuts import render_to_response

from pydici.leads.models import Lead
 
def index(request):
    latest_lead_list = Lead.objects.all().order_by("-update_date")[:5]
    return render_to_response("leads/index.html", {"latest_lead_list": latest_lead_list})

def detail(request, lead_id):
    return HttpResponse("You're looking at lead %s." % lead_id)

def csv_all(request):
    return csv_export(only_active=False)

def csv_active(request):
    return csv_export(only_active=True)

def csv_export(only_active=False):
    response = HttpResponse(mimetype="text/csv")
    response["Content-Disposition"] = "attachment; filename=plan-de-charge.csv"
    writer = csv.writer(response)
    writer.writerow(["Nom", "Description", "Client", "Suivi par", "Date de démarrage", "État",
                     "Échéance", "Staffing", "CA (k€)", "Création"])
    if only_active:
        leads=Lead.objects.exclude(state__in=("LOST", "FORGIVEN", "WIN"))
    else:
        leads=Lead.objects.all()
    for lead in leads.order_by("-update_date"):
        state=lead.get_state_display().encode("UTF-8")
        staffing=", ".join(x["trigramme"] for x in lead.staffing.values()).encode("UTF-8")
        writer.writerow([lead.name, lead.description, lead.client, lead.responsible, lead.start_date, state,
                         lead.due_date, staffing, lead.sales, lead.update_date])
    return response
