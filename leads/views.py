# coding: utf-8

import csv
from email import Message
from email.Utils import formatdate
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Encoders import encode_7or8bit

import pydici.settings

from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import Context
from django.template.loader import get_template

from pydici.leads.models import Lead
 
def index(request):
    latest_lead_list = Lead.objects.all().order_by("-update_date")[:10]
    return render_to_response("leads/index.html", {"latest_lead_list": latest_lead_list})

def summary_mail(request, html=True):
    """Ready to copy/paste in mail summary leads activity"""
    leads=Lead.objects.exclude(state__in=("LOST", "FORGIVEN", "WIN"))
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
        leads=Lead.objects.exclude(state__in=("LOST", "FORGIVEN", "WIN"))
    else:
        leads=Lead.objects.all()
    for lead in leads.order_by("-update_date"):
        state=lead.get_state_display()
        row=[lead.name, lead.client, lead.description, lead.responsible, lead.salesman, lead.start_date, state,
                         lead.due_date, lead.staffing_list(), lead.sales, lead.salesId, lead.creation_date, lead.update_date]
        row=[unicode(x).encode("UTF-8") for x in row]
        writer.writerow(row)
    return response

def send_lead_mail(request, lead_id):
    try:
        lead=Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return HttpResponse("Lead %s does not exist." % lead_id)
    template=get_template("leads/lead_mail.html")

    msgRoot = MIMEMultipart('related')
    msgRoot.set_charset("UTF-8")
    msgRoot["Date"]=formatdate()
    msgRoot["Subject"]=(u"[AVV] %s : %s" % (lead.client.organisation, lead.name)).encode("UTF-8")
    msgRoot["From"]=pydici.settings.LEADS_MAIL_FROM
    msgRoot["To"]=pydici.settings.LEADS_MAIL_TO
    msgRoot.preamble="This is a multi-part message in MIME format."

    msgAlternative = MIMEMultipart('alternative')
    msgRoot.attach(msgAlternative)

    msgText = MIMEText("Le mail au format texte n'est pas encore développé... C'est pour bientôt. La partie HTML est ok")
    msgText.set_charset("UTF-8")
    encode_7or8bit(msgText)
    msgAlternative.attach(msgText)

    msgText = MIMEText(template.render(Context({"lead" : lead, "link_root": pydici.settings.LEADS_MAIL_LINK_ROOT })).encode("UTF-8"), 'html')
    msgText.set_charset("UTF-8")
    encode_7or8bit(msgText)
    msgAlternative.attach(msgText)

    smtpConnection = smtplib.SMTP("mail.newarch.fr")
    smtpConnection.sendmail(pydici.settings.LEADS_MAIL_FROM, pydici.settings.LEADS_MAIL_TO, msgRoot.as_string())
    smtpConnection.quit()
    return HttpResponse("Lead %s was sent to %s !" % (lead_id, pydici.settings.LEADS_MAIL_TO))
