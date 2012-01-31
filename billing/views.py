# coding: utf-8
"""
Pydici billing views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta
import itertools
import mimetypes

from matplotlib.figure import Figure

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core import urlresolvers
from django.http import HttpResponseRedirect, HttpResponse
from django.db.models import Sum
from django.utils.translation import ugettext as _
from django.views.decorators.cache import cache_page

from pydici.billing.models import Bill
from pydici.leads.models import Lead
from pydici.staffing.models import Timesheet, FinancialCondition, Staffing
from pydici.crm.models import Company, BusinessBroker
from pydici.core.utils import print_png, COLORS, sortedValues, sampleList
from pydici.core.decorator import pydici_non_public

@pydici_non_public
def bill_review(request):
    """Review of bills: bills overdue, due soon, or to be created"""
    today = date.today()
    wait_warning = timedelta(15) # wait in days used to warn that a bill is due soon

    # Get bills overdue, due soon, litigious and recently paid
    overdue_bills = Bill.objects.filter(state="1_SENT").filter(due_date__lte=today).select_related()
    soondue_bills = Bill.objects.filter(state="1_SENT").filter(due_date__gt=today).filter(due_date__lte=(today + wait_warning)).select_related()
    recent_bills = Bill.objects.filter(state="2_PAID").order_by("-payment_date").select_related()[:20]
    litigious_bills = Bill.objects.filter(state="3_LITIGIOUS").select_related()

    # Compute totals
    soondue_bills_total = soondue_bills.aggregate(Sum("amount"))["amount__sum"]
    overdue_bills_total = overdue_bills.aggregate(Sum("amount"))["amount__sum"]
    litigious_bills_total = litigious_bills.aggregate(Sum("amount"))["amount__sum"]
    soondue_bills_total_with_vat = sum([bill.amount_with_vat for bill in soondue_bills if bill.amount_with_vat])
    overdue_bills_total_with_vat = sum([bill.amount_with_vat for bill in overdue_bills if bill.amount_with_vat])
    litigious_bills_total_with_vat = sum([bill.amount_with_vat for bill in litigious_bills if bill.amount_with_vat])

    # Get leads with done timesheet in past three month that don't have bill yet
    leadsWithoutBill = []
    threeMonthAgo = date.today() - timedelta(90)
    for lead in Lead.objects.filter(state="WON").select_related():
        if lead.bill_set.count() == 0:
            if Timesheet.objects.filter(mission__lead=lead, working_date__gte=threeMonthAgo).count() != 0:
                leadsWithoutBill.append(lead)

    return render_to_response("billing/bill_review.html",
                              {"overdue_bills" : overdue_bills,
                               "soondue_bills" : soondue_bills,
                               "recent_bills" : recent_bills,
                               "litigious_bills" : litigious_bills,
                               "soondue_bills_total" : soondue_bills_total,
                               "overdue_bills_total" : overdue_bills_total,
                               "litigious_bills_total" : litigious_bills_total,
                               "soondue_bills_total_with_vat" : soondue_bills_total_with_vat,
                               "overdue_bills_total_with_vat" : overdue_bills_total_with_vat,
                               "litigious_bills_total_with_vat" : litigious_bills_total_with_vat,
                               "leads_without_bill" : leadsWithoutBill,
                               "user": request.user},
                              RequestContext(request))

@pydici_non_public
def bill_payment_delay(request):
    """Report on client bill payment delay"""
    #List of tuple (company, avg delay in days)
    directDelays = list() # for direct client
    indirectDelays = list() # for client with paying authority
    for company in Company.objects.all():
        # Direct delays
        bills = Bill.objects.filter(lead__client__organisation__company=company, lead__paying_authority__isnull=True)
        res = [i.payment_delay() for i in bills]
        if res:
            directDelays.append((company, sum(res) / len(res)))
        # Indirect delays
        bills = Bill.objects.filter(lead__paying_authority__company=company)
        res = [i.payment_delay() for i in bills]
        if res:
            indirectDelays.append((company, sum(res) / len(res)))

    return render_to_response("billing/payment_delay.html",
                              {"direct_delays" : directDelays,
                               "indirect_delays" : indirectDelays,
                               "user": request.user},
                              RequestContext(request))


@pydici_non_public
def mark_bill_paid(request, bill_id):
    """Mark the given bill as paid"""
    bill = Bill.objects.get(id=bill_id)
    bill.state = "2_PAID"
    bill.save()
    return HttpResponseRedirect(urlresolvers.reverse("pydici.billing.views.bill_review"))


@pydici_non_public
def create_new_bill_from_lead(request, lead_id):
    """Create a new bill for this lead"""
    bill = Bill()
    bill.lead = Lead.objects.get(id=lead_id)
    # Define mandatory field - user will have choice to change this after
    bill.amount = 0
    bill.due_date = date.today() + timedelta(30)
    bill.state = "1_SENT"
    bill.save()
    return HttpResponseRedirect(urlresolvers.reverse("admin:billing_bill_change", args=[bill.id, ]))


@pydici_non_public
def bill_file(request, bill_id):
    """Returns bill file"""
    response = HttpResponse()
    try:
        bill = Bill.objects.get(id=bill_id)
        if bill.bill_file:
            response['Content-Type'] = mimetypes.guess_type(bill.bill_file.name)[0] or "application/stream"
            for chunk in bill.bill_file.chunks():
                response.write(chunk)
    except (Bill.DoesNotExist, OSError):
        pass

    return response



@pydici_non_public
@cache_page(60 * 10)
def graph_stat_bar(request):
    """Nice graph bar of incomming cash from bills
    @todo: per year, with start-end date"""
    billsData = {} # Bill graph Data
    tsData = {} # Timesheet done work graph data
    staffingData = {} # Staffing forecasted work graph data
    wStaffingData = {} # Weighted Staffing forecasted work graph data
    plots = [] # List of plots - needed to add legend
    today = date.today()
    start_date = today - timedelta(24 * 30) # Screen data about 24 month before today
    colors = itertools.cycle(COLORS)

    # Setting up graph
    fig = Figure(figsize=(12, 8))
    fig.set_facecolor("white")
    ax = fig.add_subplot(111)

    # Gathering billsData
    bills = Bill.objects.filter(creation_date__gt=start_date)
    if bills.count() == 0:
        return print_png(fig)

    for bill in bills:
        #Using first day of each month as key date
        kdate = bill.creation_date.replace(day=1)
        if not billsData.has_key(kdate):
            billsData[kdate] = [] # Create key with empty list
        billsData[kdate].append(bill)

    # Collect Financial conditions as a hash for further lookup
    financialConditions = {} # First key is consultant id, second is mission id. Value is daily rate
    #TODO: filter FC on timesheet date to forget old fc (perf)
    for fc in FinancialCondition.objects.filter(mission__nature="PROD"):
        if not fc.consultant_id in financialConditions:
            financialConditions[fc.consultant_id] = {} # Empty dict for missions
        financialConditions[fc.consultant_id][fc.mission_id] = fc.daily_rate

    # Collect data for done work according to timesheet data
    for ts in Timesheet.objects.filter(working_date__lt=today, working_date__gt=start_date, mission__nature="PROD").select_related():
        kdate = ts.working_date.replace(day=1)
        if not tsData.has_key(kdate):
            tsData[kdate] = 0 # Create key
        tsData[kdate] += ts.charge * financialConditions.get(ts.consultant_id, {}).get(ts.mission_id, 0) / 1000

    # Collect data for forecasted work according to staffing data
    for staffing in Staffing.objects.filter(staffing_date__gte=today.replace(day=1), mission__nature="PROD").select_related():
        kdate = staffing.staffing_date.replace(day=1)
        if not staffingData.has_key(kdate):
            staffingData[kdate] = 0 # Create key
            wStaffingData[kdate] = 0 # Create key
        staffingData[kdate] += staffing.charge * financialConditions.get(ts.consultant_id, {}).get(ts.mission_id, 0) / 1000
        wStaffingData[kdate] += staffing.charge * financialConditions.get(ts.consultant_id, {}).get(ts.mission_id, 0) * staffing.mission.probability / 100 / 1000

    # Set bottom of each graph. Starts if [0, 0, 0, ...]
    billKdates = billsData.keys()
    billKdates.sort()
    bottom = [0] * len(billKdates)

    # Draw a bar for each state
    for state in Bill.BILL_STATE:
        ydata = [sum([i.amount / 1000 for i in x if i.state == state[0]]) for x in sortedValues(billsData)]
        b = ax.bar(billKdates, ydata, bottom=bottom, align="center", width=15,
               color=colors.next())
        plots.append(b[0])
        for i in range(len(ydata)):
            bottom[i] += ydata[i] # Update bottom

    # Sort keys
    tsKdates = tsData.keys()
    tsKdates.sort()
    staffingKdates = staffingData.keys()
    staffingKdates.sort()
    wStaffingKdates = staffingData.keys()
    wStaffingKdates.sort()
    # Sort values according to keys
    tsYData = sortedValues(tsData)
    staffingYData = sortedValues(staffingData)
    wStaffingYData = sortedValues(wStaffingData)
    # Draw done work
    plots.append(ax.plot(tsKdates, tsYData, '-o', ms=10, lw=4, color="green"))
    for kdate, ydata in tsData.items():
        ax.text(kdate, ydata + 5, int(ydata))
    # Draw forecasted work
    plots.append(ax.plot(staffingKdates, staffingYData, ':o', ms=10, lw=2, color="magenta"))
    plots.append(ax.plot(wStaffingKdates, wStaffingYData, ':o', ms=10, lw=2, color="cyan"))

    # Add Legend and setup axes
    kdates = list(set(tsKdates + staffingKdates))
    ax.set_xticks(kdates)
    ax.set_xticklabels([d.strftime("%b %y") for d in kdates])
    ax.set_ylim(ymax=max(int(max(bottom)), int(max(tsYData))) + 10)
    ax.set_ylabel(u"k€")
    ax.legend(plots, [i[1] for i in Bill.BILL_STATE] + [_(u"Done work"), _(u"Forecasted work"), _(u"Weighted forecasted work")],
              bbox_to_anchor=(0., 1.02, 1., .102), loc=4,
              ncol=4, borderaxespad=0.)
    ax.grid(True)
    fig.autofmt_xdate()

    return print_png(fig)
