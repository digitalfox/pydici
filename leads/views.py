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

from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django.contrib.admin.models import LogEntry
from django.db.models import Q
from django.db import connection
from django.forms import ModelForm
from django.forms.models import inlineformset_factory

from pydici.leads.models import Lead, Consultant, SalesMan, Staffing, Mission, Holiday
from pydici.leads.utils import send_lead_mail, to_int_if_possible, working_days

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
    delay=timedelta(days=9)

    new_active_leads=Lead.objects.active().filter(update_date__gte=(today-delay)).order_by("state", "-update_date")
    old_active_leads=Lead.objects.active().filter(update_date__lt=(today-delay)).order_by("state", "-update_date")
    passive_leads=Lead.objects.passive().filter(update_date__gte=(today-delay)).exclude(state="SLEEPING")
    passive_leads=passive_leads.order_by("state", "-update_date")
    if html:
        return render_to_response("leads/mail.html", {"lead_group": [passive_leads, new_active_leads, old_active_leads] })
    else:
        return render_to_response("leads/mail.txt", {"lead_group": [passive_leads, new_active_leads, old_active_leads] },
                                  mimetype="text/plain; charset=utf-8")

@login_required
def detail(request, lead_id):
    """Lead detailed description"""
    try:
        lead=Lead.objects.get(id=lead_id)
        actionList = LogEntry.objects.filter(object_id = lead_id,
                                              content_type__name="lead")
        actionList=actionList.select_related().order_by('action_time')
         # Lead rank in active list
        active_leads=Lead.objects.active().order_by("creation_date", "id")
        try:
            rank=[l.id for l in active_leads].index(lead.id)+1
        except ValueError:
            # Lead is not in active list, rank it to zero
            rank=0
    except Lead.DoesNotExist:
        raise Http404
    return render_to_response("leads/lead_detail.html", {"lead": lead,
                                                         "active_count": active_leads.count(),
                                                         "active_rank" : rank,
                                                         "link_root": pydici.settings.LEADS_WEB_LINK_ROOT,
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
                                                    "active_leads" : Lead.objects.active().order_by("creation_date", "id"),
                                                    "user": request.user })


def missions(request, onlyActive=True):
    """List of missions"""
    if onlyActive:
        missions=Mission.objects.filter(active=True)
        all=False
    else:
        missions=Mission.objects.all()
        all=True
    return render_to_response("leads/missions.html", {"missions": missions,
                                                      "all": all,
                                                      "user": request.user })
    


def mission_staffing(request, mission_id):
    """Edit mission staffing"""
    StaffingFormSet=inlineformset_factory(Mission, Staffing)
    mission=Mission.objects.get(id=mission_id)
    if request.method == "POST":
        formset = StaffingFormSet(request.POST, instance=mission)
        if formset.is_valid():
            formset.save()
            formset=StaffingFormSet(instance=mission) # Recreate a new form for next update
    else:
        formset=StaffingFormSet(instance=mission) # An unbound form
    
    consultants=set([s.consultant for s in mission.staffing_set.all()])
    consultants=list(consultants)
    consultants.sort(cmp=lambda x,y: cmp(x.name, y.name))
    return render_to_response('leads/mission_staffing.html', {"formset": formset,
                                                              "mission": mission,
                                                              "consultants": consultants,
                                                              "user": request.user
                                                              })


def consultant_staffing(request, consultant_id):
    """Edit consultant staffing"""
    StaffingFormSet=inlineformset_factory(Consultant, Staffing)
    consultant=Consultant.objects.get(id=consultant_id)
    if request.method == "POST":
        formset = StaffingFormSet(request.POST, instance=consultant)
        if formset.is_valid():
            formset.save()
            formset=StaffingFormSet(instance=consultant) # Recreate a new form for next update
    else:
        formset=StaffingFormSet(instance=consultant) # An unbound form
        
    missions=set([s.mission for s in consultant.staffing_set.all()])
    missions=list(missions)
    missions.sort(cmp=lambda x,y: cmp(x.lead, y.lead))

    return render_to_response('leads/consultant_staffing.html', {"formset": formset,
                                                              "consultant": consultant,
                                                              "missions": missions,
                                                              "user": request.user
                                                              })

def pdc_review(request, year=None, month=None, n_month=4):
    """PDC overview
    @param year: start date year. None means current year
    @param year: start date year. None means current month
    @param n_month: number of month displays"""
    if year and month:
        start_date=date(int(year), int(month), 1)
    else:
        start_date=date.today()
        start_date=start_date.replace(day=1) # We use the first day to represent month

    staffing={} # staffing data per month and per consultant
    total={}    # total staffing data per month
    rates=[]     # staffing rates per month
    available_month={} # available working days per month
    months=[]   # list of month to be displayed
    people=Consultant.objects.count()
    for i in range(int(n_month)):
        months.append(start_date.replace(month=start_date.month+i))

    # Initialize total dict and available dict
    holidays_days=Holiday.objects.all()
    for month in months:
        total[month]={"prod":0, "unprod":0, "holidays":0, "available":0}
        available_month[month]=working_days(month, holidays_days)

    # Get consultants staffing
    for consultant in Consultant.objects.all():
        staffing[consultant]=[]
        for month in months:
            current_staffing=consultant.staffing_set.filter(staffing_date=month)
            prod=to_int_if_possible(sum(i.charge for i in current_staffing.filter(mission__nature="PROD")))
            unprod=to_int_if_possible(sum(i.charge for i in current_staffing.filter(mission__nature="NONPROD")))
            holidays=to_int_if_possible(sum(i.charge for i in current_staffing.filter(mission__nature="HOLIDAYS")))
            available=available_month[month]-(prod+unprod+holidays)
            staffing[consultant].append([prod, unprod, holidays, available])
            total[month]["prod"]+=prod
            total[month]["unprod"]+=unprod
            total[month]["holidays"]+=holidays
            total[month]["available"]+=available

    # Compute indicator rates
    for month in months:
        rate=[]
        for indicator in ("prod", "unprod", "holidays"):
            rate.append(100*total[month][indicator]/(people*available_month[month]))
        rate.append(100*total[month]["available"]/(total[month]["available"]+total[month]["prod"]+total[month]["unprod"]))
        rates.append(map(lambda x: round(x, 1), rate))
    # Format total dict into list
    total=total.items()
    total.sort(cmp=lambda x, y:cmp(x[0], y[0])) # Sort according date
    # Remove date, and transform dict into ordered list:
    total=[(i[1]["prod"], i[1]["unprod"], i[1]["holidays"], i[1]["available"]) for i in total]
    #TODO: add production rate
    return render_to_response("leads/pdc_review.html", {"staffing": staffing,
                                                        "months": months,
                                                        "consultants": Consultant.objects.all(),
                                                        "total": total,
                                                        "rates": rates,
                                                        "user": request.user}
                                                        )

    
def IA_stats(request):
    """Statistics about IA performance (hé hé)
    @todo: make it per year"""

    leadData={} # Lead data group by month
    salesMenData={} # Leads by state group by month for each salesman
    salesMen=list(SalesMan.objects.all()) + [None]

    # Gathering data
    for lead in Lead.objects.all():
        #Using first day of each month as key date
        kdate=date(lead.creation_date.year, lead.creation_date.month, 1)
        if not leadData.has_key(kdate):
            leadData[kdate]=[] # Create key with empty list
        leadData[kdate].append(lead)

    # Years of data
    years=range(min(leadData.keys()).year, max(leadData.keys()).year+1)

    data={}
    for year in years:
        data[year]={}
        leadSum={}
        for salesMan in salesMen:
            data[year][salesMan]={}
            for month in range(1, 13):
                if not leadSum.has_key(month):
                    leadSum[month]={}
                data[year][salesMan][month]={}
                for state, label in (("LOST", "P"), ("WIN", "G"), ("FORGIVEN", "A")):
                    leads=leadData.get(date(year=year, month=month, day=1), [])
                    n=len([lead for lead in leads if (lead.state==state and lead.salesman==salesMan)])
                    data[year][salesMan][month][label]=n
                    if not leadSum[month].has_key(label):
                        leadSum[month][label]=0
                    leadSum[month][label]+=n
        data[year]["Total"]=leadSum

    return render_to_response("leads/IA_stats.html", {"data": data})

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

    return print_png(fig)

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

    return print_png(fig)

def graph_stat_salesmen(request):
    """Nice graph bar of lead per IA during time using matplotlib
    @todo: per year, with start-end date"""
    data={} # Graph data
    lines=[] # List of lines - needed to add legend
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

    ymax=0
    # Draw a bar for each state
    salesMen=list(SalesMan.objects.all()) + [None]
    for salesMan in salesMen:
        if len(colors)==0:
            colors=list(COLORS)
        color=colors.pop()
        for state, style in (("LOST", "--^"), ("WIN", "-o")):
            ydata=[len([i for i in x if (i.state==state and i.salesman==salesMan)]) for x in data.values()]
            line=ax.plot(data.keys(), ydata, style, color=color)
            if max(ydata)>ymax:
                ymax=max(ydata)
        lines.append(line)

    # Add Legend and setup axes
    ax.set_xticks(data.keys())
    ax.set_xticklabels(data.keys())
    ax.set_ylim(ymax=ymax+10)
    ax.legend(lines, [i.name for i in SalesMan.objects.all()]+["Aucun"])
    ax.set_title(u"Suivi des leads par IA (trait plein : aff. gagnées. Pointillés : aff. perdues)")

    return print_png(fig)

def print_png(fig):
    """Return http response with fig rendered as png
    @param fig: fig to render
    @type fig: matplotlib.Figure
    @return: HttpResponse"""
    canvas=FigureCanvas(fig)
    response=HttpResponse(content_type='image/png')
    canvas.print_png(response)
    return response
