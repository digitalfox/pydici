# coding: utf-8
"""
Django views. All http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""
import csv
from datetime import datetime, timedelta, date
import os

os.environ['MPLCONFIGDIR'] = '/tmp' # Needed for matplotlib

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

import pydici.settings

from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.admin.models import LogEntry
from django.db.models import Q
from django.db import connection
from django.forms import ModelForm
from django.forms.models import inlineformset_factory, BaseInlineFormSet
from django.utils.translation import ugettext as _

from pydici.leads.models import Lead, Consultant, SalesMan, Staffing, Mission, Holiday
from pydici.leads.utils import send_lead_mail, to_int_or_round, working_days

# Graph colors
COLORS = ["#05467A", "#FF9900", "#A7111B", "#DAEBFF", "#FFFF6D", "#AAFF86", "#D972FF", "#FF8D8F"]

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

def summary_mail(request, html=True):
    """Ready to copy/paste in mail summary leads activity"""
    today = datetime.today()
    delay = timedelta(days=6)
    leads = []
    for state in ("WIN", "FORGIVEN", "LOST", "WRITE_OFFER", "OFFER_SENT", "NEGOCATION", "QUALIF"):
        rs = Lead.objects.filter(state=state).order_by("-update_date")
        if state in ("WIN", "FORGIVEN", "LOST"):
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
        active_leads = Lead.objects.active().order_by("start_date", "creation_date", "id")
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
        except ValueError:
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
                                                       _(u"Sales (k€)"), _("Deal Id"), _("Creation"),
                                                       _("Updated")]])
    if target != "all":
        leads = Lead.objects.active()
    else:
        leads = Lead.objects.all()
    for lead in leads.order_by("start_date"):
        state = lead.get_state_display()
        row = [lead.name, lead.client, lead.description, lead.responsible, lead.salesman, lead.start_date, state,
                         lead.due_date, lead.staffing_list(), lead.sales, lead.salesId, lead.creation_date, lead.update_date]
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
                                                      Q(state="WIN", salesId="") |
                                                      Q(state="SLEEPING"))
    recentArchivedLeads = recentArchivedLeads.order_by("state", "-update_date")
    return render_to_response("leads/review.html", {"recent_archived_leads" : recentArchivedLeads,
                                                    "active_leads" : Lead.objects.active().order_by("start_date", "id"),
                                                    "user": request.user })


def missions(request, onlyActive=True):
    """List of missions"""
    if onlyActive:
        missions = Mission.objects.filter(active=True)
        all = False
    else:
        missions = Mission.objects.all()
        all = True
    return render_to_response("leads/missions.html", {"missions": missions,
                                                      "all": all,
                                                      "user": request.user })


@permission_required("leads.add_staffing")
@permission_required("leads.change_staffing")
@permission_required("leads.delete_staffing")
def mission_staffing(request, mission_id):
    """Edit mission staffing"""
    StaffingFormSet = inlineformset_factory(Mission, Staffing,
                                          fields=("consultant", "staffing_date", "charge", "comment"))
    mission = Mission.objects.get(id=mission_id)
    if request.method == "POST":
        formset = StaffingFormSet(request.POST, instance=mission)
        if formset.is_valid():
            saveFormsetAndLog(formset, request)
            formset = StaffingFormSet(instance=mission) # Recreate a new form for next update
    else:
        formset = StaffingFormSet(instance=mission) # An unbound form

    consultants = set([s.consultant for s in mission.staffing_set.all()])
    consultants = list(consultants)
    consultants.sort(cmp=lambda x, y: cmp(x.name, y.name))
    return render_to_response('leads/mission_staffing.html', {"formset": formset,
                                                              "mission": mission,
                                                              "consultants": consultants,
                                                              "user": request.user
                                                              })


class ActiveStaffingInlineFormSet(BaseInlineFormSet):
    """Custom inline formset used to override queryset
    and get ride of inactive mission staffing"""
    def get_queryset(self):
        lastMonth = datetime.today() - timedelta(days=30)
        qs = super(ActiveStaffingInlineFormSet, self).get_queryset()
        qs = qs.filter(mission__active=True) # Remove archived mission
        qs = qs.exclude(Q(staffing_date__lte=lastMonth) &
                  ~ Q(mission__nature="PROD")) # Remove past non prod mission
        return qs

def consultant_staffing(request, consultant_id):
    """Edit consultant staffing"""
    consultant = Consultant.objects.get(id=consultant_id)

    if not (request.user.has_perm("leads.add_staffing") and
            request.user.has_perm("leads.change_staffing") and
            request.user.has_perm("leads.delete_staffing")):
        # Only forbid access if the user try to edit someone else staffing
        if request.user.username.upper() != consultant.trigramme:
            return HttpResponseRedirect("/leads/forbiden")

    StaffingFormSet = inlineformset_factory(Consultant, Staffing,
                                          formset=ActiveStaffingInlineFormSet,
                                          fields=("mission", "staffing_date", "charge", "comment"))

    if request.method == "POST":
        formset = StaffingFormSet(request.POST, instance=consultant)
        if formset.is_valid():
            saveFormsetAndLog(formset, request)
            formset = StaffingFormSet(instance=consultant) # Recreate a new form for next update
    else:
        formset = StaffingFormSet(instance=consultant) # An unbound form

    missions = set([s.mission for s in consultant.staffing_set.all() if s.mission.active])
    missions = list(missions)
    missions.sort(cmp=lambda x, y: cmp(x.lead, y.lead))

    return render_to_response('leads/consultant_staffing.html', {"formset": formset,
                                                              "consultant": consultant,
                                                              "missions": missions,
                                                              "user": request.user
                                                              })


def pdc_review(request, year=None, month=None):
    """PDC overview
    @param year: start date year. None means current year
    @param year: start date year. None means curre    nt month"""

    # Don't display this page if no productive consultant are defined
    if Consultant.objects.filter(productive=True).count() == 0:
        #TODO: make this message nice
        return HttpResponse(_("No productive consultant defined !"))

    n_month = 3
    if "n_month" in request.GET:
        try:
            n_month = int(request.GET["n_month"])
            if n_month > 12:
                n_month = 12 # Limit to 12 month to avoid complex and useless month list computation
        except ValueError:
            pass

    if "projected" in request.GET:
        projected = True
    else:
        projected = False

    groupby = "manager"
    if "groupby" in request.GET:
        if request.GET["groupby"] in ("manager", "position"):
            groupby = request.GET["groupby"]

    if year and month:
        start_date = date(int(year), int(month), 1)
    else:
        start_date = date.today()
        start_date = start_date.replace(day=1) # We use the first day to represent month

    staffing = {} # staffing data per month and per consultant
    total = {}    # total staffing data per month
    rates = []     # staffing rates per month
    available_month = {} # available working days per month
    months = []   # list of month to be displayed
    people = Consultant.objects.filter(productive=True).count()

    for i in range(n_month):
        if start_date.month + i <= 12:
            months.append(start_date.replace(month=start_date.month + i))
        else:
            # We wrap around a year (max one year)
            months.append(start_date.replace(month=start_date.month + i - 12, year=start_date.year + 1))

    previous_slice_date = start_date - timedelta(days=31 * n_month)
    next_slice_date = start_date + timedelta(days=31 * n_month)

    # Initialize total dict and available dict
    holidays_days = Holiday.objects.all()
    for month in months:
        total[month] = {"prod":0, "unprod":0, "holidays":0, "available":0}
        available_month[month] = working_days(month, holidays_days)

    # Get consultants staffing
    for consultant in Consultant.objects.select_related().filter(productive=True):
        staffing[consultant] = []
        missions = set()
        for month in months:
            if projected:
                current_staffings = consultant.staffing_set.filter(staffing_date=month).order_by()
            else:
                # Only keep 100% mission
                current_staffings = consultant.staffing_set.filter(staffing_date=month, mission__probability=100).order_by()

            # Sum staffing
            prod = []
            unprod = []
            holidays = []
            for current_staffing  in current_staffings:
                nature = current_staffing.mission.nature
                if nature == "PROD":
                    missions.add(current_staffing.mission) # Store prod missions for this consultant
                    prod.append(current_staffing.charge * current_staffing.mission.probability / 100)
                elif nature == "NONPROD":
                    unprod.append(current_staffing.charge * current_staffing.mission.probability / 100)
                elif nature == "HOLIDAYS":
                    holidays.append(current_staffing.charge * current_staffing.mission.probability / 100)

            # Staffing computation
            prod = to_int_or_round(sum(prod))
            unprod = to_int_or_round(sum(unprod))
            holidays = to_int_or_round(sum(holidays))
            available = available_month[month] - (prod + unprod + holidays)
            staffing[consultant].append([prod, unprod, holidays, available])
            total[month]["prod"] += prod
            total[month]["unprod"] += unprod
            total[month]["holidays"] += holidays
            total[month]["available"] += available
        # Add mission synthesis to staffing dict
        staffing[consultant].append([", ".join(["<a href='/leads/mission/%s'>%s</a>" % (m.id, m.short_name()) for m in list(missions)])])

    # Compute indicator rates
    for month in months:
        rate = []
        ndays = people * available_month[month] # Total days for this month
        for indicator in ("prod", "unprod", "holidays", "available"):
            if indicator == "holidays":
                rate.append(100.0 * total[month][indicator] / ndays)
            else:
                rate.append(100.0 * total[month][indicator] / (ndays - total[month]["holidays"]))
        rates.append(map(lambda x: to_int_or_round(x), rate))

    # Format total dict into list
    total = total.items()
    total.sort(cmp=lambda x, y:cmp(x[0], y[0])) # Sort according date
    # Remove date, and transform dict into ordered list:
    total = [(to_int_or_round(i[1]["prod"]),
            to_int_or_round(i[1]["unprod"]),
            to_int_or_round(i[1]["holidays"]),
            to_int_or_round(i[1]["available"])) for i in total]

    # Order staffing list
    staffing = staffing.items()
    staffing.sort(cmp=lambda x, y:cmp(x[0].name, y[0].name)) # Sort by name
    if groupby == "manager":
        staffing.sort(cmp=lambda x, y:cmp(unicode(x[0].manager), unicode(y[0].manager))) # Sort by manager
    else:
        staffing.sort(cmp=lambda x, y:cmp(x[0].profil, y[0].profil)) # Sort by position

    return render_to_response("leads/pdc_review.html", {"staffing": staffing,
                                                        "months": months,
                                                        "total": total,
                                                        "rates": rates,
                                                        "user": request.user,
                                                        "projected": projected,
                                                        "previous_slice_date" : previous_slice_date,
                                                        "next_slice_date" : next_slice_date,
                                                        "start_date" : start_date,
                                                        "groupby" : groupby}
                                                        )

def deactivate_mission(request, mission_id):
    """Deactivate the given mission"""
    mission = Mission.objects.get(id=mission_id)
    mission.active = False
    mission.save()
    return HttpResponseRedirect("/leads/mission/")


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
                for state, label in (("LOST", "P"), ("WIN", "G"), ("FORGIVEN", "A")):
                    leads = leadData.get(date(year=year, month=month, day=1), [])
                    n = len([lead for lead in leads if (lead.state == state and lead.salesman == salesMan)])
                    data[year][salesMan][month][label] = n
                    if not leadSum[month].has_key(label):
                        leadSum[month][label] = 0
                    leadSum[month][label] += n
        data[year]["Total"] = leadSum

    return render_to_response("leads/IA_stats.html", {"data": data})

def graph_stat_pie(request):
    """Nice graph pie of lead state repartition using matplotlib
    @todo: per year, with start-end date"""
    stateDict = dict(Lead.STATES)
    cursor = connection.cursor()
    cursor.execute("select  state, count(*) from leads_lead  group by state")
    data = cursor.fetchall()
    fig = Figure(figsize=(8, 8))
    fig.set_facecolor("white")
    ax = fig.add_subplot(111)
    ax.pie([x[1] for x in data], colors=COLORS, labels=["%s\n(%s)" % (stateDict[x[0]], x[1]) for x in data], shadow=True, autopct='%1.1f%%')

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
               color=colors.pop())
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
        for state, style in (("LOST", "--^"), ("WIN", "-o")):
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

def print_png(fig):
    """Return http response with fig rendered as png
    @param fig: fig to render
    @type fig: matplotlib.Figure
    @return: HttpResponse"""
    canvas = FigureCanvas(fig)
    response = HttpResponse(content_type='image/png')
    canvas.print_png(response)
    return response

def saveFormsetAndLog(formset, request):
    """Save the given staffing formset and log last user"""
    now = datetime.now()
    staffings = formset.save(commit=False)
    for staffing in staffings:
        staffing.last_user = unicode(request.user)
        staffing.update_date = now
        staffing.save()
