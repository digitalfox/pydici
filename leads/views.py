# coding: utf-8
"""
Django views. All http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: BSD
"""
import csv
from datetime import datetime, timedelta, date
import os

os.environ['MPLCONFIGDIR']='/tmp' # Needed for matplotlib

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

import pydici.settings

from django.http import HttpResponse, Http404
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django.contrib.admin.models import LogEntry
from django.db.models import Q
from django.db import connection

from pydici.leads.models import Lead, Consultant, SalesMan
from pydici.leads.utils import send_lead_mail

# Graph colors
COLORS=["#05467A", "#FF9900", "#A7111B", "#DAEBFF", "#FFFF6D", "#AAFF86", "#D972FF", "#FF8D8F"]

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
        myLatestArchivedLeads=set((consultant.lead_responsible.passive().order_by("-update_date")
                                  |consultant.lead_set.passive().order_by("-update_date"))[:10])

    salesmen=SalesMan.objects.filter(trigramme__iexact=request.user.username)
    if salesmen:
        salesman=salesmen[0]
        myLeadsAsResponsible.update(salesman.lead_set.active())
        myLatestArchivedLeads.update(salesman.lead_set.passive().order_by("-update_date")[:10])


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
    passive_leads=Lead.objects.passive().filter(update_date__gte=(today-delay)).exclude(state="SLEEPING")
    passive_leads=passive_leads.order_by("state", "-update_date")
    if html:
        return render_to_response("leads/mail.html", {"lead_group": [passive_leads, active_leads] })
    else:
        return render_to_response("leads/mail.txt", {"lead_group": [passive_leads, active_leads] },
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

def graph_stat_pie(request):
    """Nice graph pie of lead state repartition using matplotlib
    @todo: per year, with start-end date"""
    stateDict=dict(Lead.STATES)
    cursor=connection.cursor()
    cursor.execute("select  state, count(*) from leads_lead  group by state")
    data=cursor.fetchall()
    fig=Figure(figsize=(8,8))
    ax=fig.add_subplot(111)
    ax.pie([x[1] for x in data], colors=COLORS, labels=["%s\n(%s)" % (stateDict[x[0]], x[1]) for x in data], shadow=True, autopct='%1.1f%%')
    canvas=FigureCanvas(fig)
    response=HttpResponse(content_type='image/png')
    canvas.print_png(response)
    return response

def graph_stat_bar(request):
    """Nice graph bar of lead state during time using matplotlib
    @todo: per year, with start-end date"""
    data={} # Graph data
    bars=[] # List of bars - needed to add legend
    colors=list(COLORS)

    # Gathering data
    for lead in Lead.objects.all():
        #Using first day of each month as key date
        kdate=date(lead.creation_date.year, lead.creation_date.month, 1)
        if not data.has_key(kdate):
            data[kdate]=[] # Create key with empty list
        data[kdate].append(lead)

    # Setting up graph
    fig=Figure(figsize=(8,8))
    ax=fig.add_subplot(111)
    bottom=[0]*len(data.keys()) # Bottom of each graph. Starts if [0, 0, 0, ...]

    # Draw a bar for each state
    for state in Lead.STATES:
        ydata=[len([i for i in x if i.state==state[0]]) for x in data.values()]
        b=ax.bar(data.keys(), ydata, bottom=bottom, align="center", width=15,
               color=colors.pop())
        bars.append(b[0])
        for i in range(len(ydata)):
            bottom[i]+=ydata[i] # Update bottom

    # Add Legend and setup axes
    ax.set_xticks(data.keys())
    ax.set_xticklabels(data.keys())
    ax.set_ylim(ymax=max(bottom)+10)
    ax.legend(bars, [i[1] for i in Lead.STATES])

    # Send response to user
    canvas=FigureCanvas(fig)
    response=HttpResponse(content_type='image/png')
    canvas.print_png(response)
    return response