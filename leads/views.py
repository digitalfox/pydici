# coding: utf-8
"""
Pydici leads views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

import csv
from datetime import datetime, timedelta
import os

os.environ['MPLCONFIGDIR'] = '/tmp' # Needed for matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure


from django.contrib.auth.decorators import login_required
from django.contrib.admin.models import LogEntry
from django.shortcuts import render_to_response
from django.http import HttpResponse, Http404
from django.db.models import Q
from django.utils.translation import ugettext as _

from pydici.leads.models import Lead
import pydici.settings


# Graph colors
COLORS = ["#05467A", "#FF9900", "#A7111B", "#DAEBFF", "#FFFF6D", "#AAFF86", "#D972FF", "#FF8D8F"]


def summary_mail(request, html=True):
    """Ready to copy/paste in mail summary leads activity"""
    today = datetime.today()
    delay = timedelta(days=6) # Six days
    leads = []
    for state in ("WON", "FORGIVEN", "LOST", "SLEEPING", "WRITE_OFFER", "OFFER_SENT", "NEGOTIATION", "QUALIF"):
        rs = Lead.objects.filter(state=state).order_by("-update_date")
        if state in ("WON", "FORGIVEN", "LOST", "SLEEPING"):
            rs = rs.filter(update_date__gte=(today - delay))
        leads.append(rs)
    if html:
        return render_to_response("leads/mail.html", {"lead_group": leads })
    else:
        return render_to_response("leads/mail.txt", {"lead_group": leads },
                                  mimetype="text/plain; charset=utf-8")

@login_required
def detail(request, lead_id):
    """Lead detailed description"""
    try:
        lead = Lead.objects.get(id=lead_id)
        actionList = LogEntry.objects.filter(object_id=lead_id,
                                              content_type__name="lead")
        actionList = actionList.select_related().order_by('action_time')
        # Lead rank in active list
        active_leads = Lead.objects.active().order_by("creation_date")
        try:
            rank = [l.id for l in active_leads].index(lead.id)
            active_count = active_leads.count()
            if rank == 0:
                previous_lead = None
                next_lead = active_leads[1]
            elif rank + 1 >= active_count:
                previous_lead = active_leads[rank - 1]
                next_lead = None
            else:
                previous_lead = active_leads[rank - 1]
                next_lead = active_leads[rank + 1]
        except (ValueError, IndexError):
            # Lead is not in active list, rank it to zero
            rank = 0
            next_lead = None
            previous_lead = None
            active_count = None

    except Lead.DoesNotExist:
        raise Http404
    return render_to_response("leads/lead_detail.html", {"lead": lead,
                                                         "active_count": active_count,
                                                         "active_rank" : rank + 1,
                                                         "next_lead" : next_lead,
                                                         "previous_lead" : previous_lead,
                                                         "link_root": pydici.settings.LEADS_WEB_LINK_ROOT,
                                                         "action_list": actionList,
                                                         "user": request.user})

def csv_export(request, target):
    response = HttpResponse(mimetype="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s" % _("leads.csv")
    writer = csv.writer(response, delimiter=';')
    writer.writerow([i.encode("ISO-8859-15") for i in [_("Name"), _("Client"), _("Description"),
                                                       _("Managed by"), _("Salesman"), _("Starting"),
                                                       _("State"), _("Due date"), _("Staffing"),
                                                       _(u"Sales (k€)"), _("Creation"),
                                                       _("Updated")]])
    if target != "all":
        leads = Lead.objects.active()
    else:
        leads = Lead.objects.all()
    for lead in leads.order_by("creation_date"):
        state = lead.get_state_display()
        row = [lead.name, lead.client, lead.description, lead.responsible, lead.salesman, lead.start_date, state,
                         lead.due_date, lead.staffing_list(), lead.sales, lead.creation_date, lead.update_date]
        row = [unicode(x).encode("ISO-8859-15", "ignore") for x in row]
        writer.writerow(row)
    return response

def mail_lead(request, lead_id=0):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        raise Http404
    try:
        send_lead_mail(lead)
        return HttpResponse(_("Lead %(id)s was sent to %(mail)s !") % { "id": lead_id,
                                                                       "mail": pydici.settings.LEADS_MAIL_TO})
    except Exception, e:
        return HttpResponse(_("Failed to send mail: %s") % e)

def review(request):
    today = datetime.today()
    delay = timedelta(days=10) #(10 days)
    recentArchivedLeads = Lead.objects.passive().filter(Q(update_date__gte=(today - delay)) |
                                                      Q(state="SLEEPING"))
    recentArchivedLeads = recentArchivedLeads.order_by("state", "-update_date")
    return render_to_response("leads/review.html", {"recent_archived_leads" : recentArchivedLeads,
                                                    "active_leads" : Lead.objects.active().order_by("creation_date"),
                                                    "user": request.user })


def graph_stat_pie(request):
    """Nice graph pie of lead state repartition using matplotlib
    @todo: per year, with start-end date"""
    stateDict = dict(Lead.STATES)
    states = [i[0] for i in Lead.STATES]
    cursor = connection.cursor()
    cursor.execute("select  state, count(*) from leads_lead  group by state")
    data = list(cursor.fetchall())
    data.sort(cmp=lambda x, y: cmp(states.index(x[0]), states.index(y[0])))
    fig = Figure(figsize=(8, 8))
    fig.set_facecolor("white")
    ax = fig.add_subplot(111)
    ax.pie([x[1] for x in data], colors=COLORS,
           labels=["%s\n(%s)" % (stateDict[x[0]], x[1]) for x in data],
           shadow=True, autopct='%1.1f%%')

    return print_png(fig)

def graph_stat_bar(request):
    """Nice graph bar of lead state during time using matplotlib
    @todo: per year, with start-end date"""
    data = {} # Graph data
    bars = [] # List of bars - needed to add legend
    colors = list(COLORS)

    # Gathering data
    for lead in Lead.objects.all():
        #Using first day of each month as key date
        kdate = date(lead.creation_date.year, lead.creation_date.month, 1)
        if not data.has_key(kdate):
            data[kdate] = [] # Create key with empty list
        data[kdate].append(lead)

    # Setting up graph
    fig = Figure(figsize=(8, 8))
    fig.set_facecolor("white")
    ax = fig.add_subplot(111)
    bottom = [0] * len(data.keys()) # Bottom of each graph. Starts if [0, 0, 0, ...]

    # Draw a bar for each state
    for state in Lead.STATES:
        ydata = [len([i for i in x if i.state == state[0]]) for x in data.values()]
        b = ax.bar(data.keys(), ydata, bottom=bottom, align="center", width=15,
               color=colors.pop(0))
        bars.append(b[0])
        for i in range(len(ydata)):
            bottom[i] += ydata[i] # Update bottom

    # Add Legend and setup axes
    ax.set_xticks(data.keys())
    ax.set_xticklabels(data.keys())
    ax.set_ylim(ymax=max(bottom) + 10)
    ax.legend(bars, [i[1] for i in Lead.STATES])
    fig.autofmt_xdate()

    return print_png(fig)

def graph_stat_salesmen(request):
    """Nice graph bar of lead per IA during time using matplotlib
    @todo: per year, with start-end date"""
    data = {} # Graph data
    lines = [] # List of lines - needed to add legend
    colors = list(COLORS)

    # Gathering data
    for lead in Lead.objects.all():
        #Using first day of each month as key date
        kdate = date(lead.creation_date.year, lead.creation_date.month, 1)
        if not data.has_key(kdate):
            data[kdate] = [] # Create key with empty list
        data[kdate].append(lead)

    # Setting up graph
    fig = Figure(figsize=(8, 8))
    ax = fig.add_subplot(111)

    ymax = 0
    # Draw a bar for each state
    salesMen = list(SalesMan.objects.all()) + [None]
    for salesMan in salesMen:
        if len(colors) == 0:
            colors = list(COLORS)
        color = colors.pop()
        for state, style in (("LOST", "--^"), ("WON", "-o")):
            ydata = [len([i for i in x if (i.state == state and i.salesman == salesMan)]) for x in data.values()]
            line = ax.plot(data.keys(), ydata, style, color=color)
            if max(ydata) > ymax:
                ymax = max(ydata)
        lines.append(line)

    # Add Legend and setup axes
    ax.set_xticks(data.keys())
    ax.set_xticklabels(data.keys())
    ax.set_ylim(ymax=ymax + 10)
    ax.legend(lines, [i.name for i in SalesMan.objects.all()] + ["Aucun"])
    ax.set_title(_("Leads per salesmen (solid line: won. Dotted line: lost)"))

    return print_png(fig)


def IA_stats(request):
    """Statistics about IA performance (hé hé)
    @todo: make it per year"""

    leadData = {} # Lead data group by month
    salesMenData = {} # Leads by state group by month for each salesman
    salesMen = list(SalesMan.objects.all()) + [None]

    # Gathering data
    for lead in Lead.objects.all():
        #Using first day of each month as key date
        kdate = date(lead.creation_date.year, lead.creation_date.month, 1)
        if not leadData.has_key(kdate):
            leadData[kdate] = [] # Create key with empty list
        leadData[kdate].append(lead)

    # Years of data
    years = range(min(leadData.keys()).year, max(leadData.keys()).year + 1)

    data = {}
    for year in years:
        data[year] = {}
        leadSum = {}
        for salesMan in salesMen:
            data[year][salesMan] = {}
            for month in range(1, 13):
                if not leadSum.has_key(month):
                    leadSum[month] = {}
                data[year][salesMan][month] = {}
                for state, label in (("LOST", "P"), ("WON", "G"), ("FORGIVEN", "A")):
                    leads = leadData.get(date(year=year, month=month, day=1), [])
                    n = len([lead for lead in leads if (lead.state == state and lead.salesman == salesMan)])
                    data[year][salesMan][month][label] = n
                    if not leadSum[month].has_key(label):
                        leadSum[month][label] = 0
                    leadSum[month][label] += n
        data[year]["Total"] = leadSum

    return render_to_response("leads/IA_stats.html", {"data": data})


def print_png(fig):
    """Return http response with fig rendered as png
    @param fig: fig to render
    @type fig: matplotlib.Figure
    @return: HttpResponse"""
    canvas = FigureCanvas(fig)
    response = HttpResponse(content_type='image/png')
    canvas.print_png(response)
    return response
