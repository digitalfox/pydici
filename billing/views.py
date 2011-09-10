# coding: utf-8
"""
Pydici billing views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta
import itertools

from matplotlib.figure import Figure

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core import urlresolvers
from django.http import HttpResponseRedirect
from django.db.models import Sum
from django.utils.translation import ugettext as _

from pydici.billing.models import Bill
from pydici.leads.models import Lead
from pydici.staffing.models import Timesheet, FinancialCondition
from pydici.crm.models import ClientCompany, BusinessBroker
from pydici.core.utils import print_png, COLORS, sortedValues

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
                               "leads_without_bill" : leadsWithoutBill,
                               "user": request.user},
                              RequestContext(request))

def bill_payment_delay(request):
    """Report on client bill payment delay"""
    #List of tuple (company, avg delay in days)
    directDelays = list() # for direct client
    indirectDelays = list() # for client with paying authority
    for company in ClientCompany.objects.all():
        bills = Bill.objects.filter(lead__client__organisation__company=company, lead__paying_authority__isnull=True)
        res = [i.payment_delay() for i in bills]
        if res:
            directDelays.append((company, sum(res) / len(res)))

    for authority in BusinessBroker.objects.all():
        bills = Bill.objects.filter(lead__paying_authority=authority)
        res = [i.payment_delay() for i in bills]
        if res:
            indirectDelays.append((authority, sum(res) / len(res)))

    return render_to_response("billing/payment_delay.html",
                              {"direct_delays" : directDelays,
                               "indirect_delays" : indirectDelays,
                               "user": request.user},
                              RequestContext(request))


def mark_bill_paid(request, bill_id):
    """Mark the given bill as paid"""
    bill = Bill.objects.get(id=bill_id)
    bill.state = "2_PAID"
    bill.save()
    return HttpResponseRedirect(urlresolvers.reverse("pydici.billing.views.bill_review"))

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

def graph_stat_bar(request):
    """Nice graph bar of incomming cash from bills
    @todo: per year, with start-end date"""
    billsData = {} # Bill graph Data
    tsData = {} # Timesheet  done work graph data
    plots = [] # List of plots - needed to add legend
    colors = itertools.cycle(COLORS)

    # Setting up graph
    fig = Figure(figsize=(12, 8))
    fig.set_facecolor("white")
    ax = fig.add_subplot(111)

    # Gathering billsData
    bills = Bill.objects.all()
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
    for fc in FinancialCondition.objects.all():
        if not fc.consultant_id in financialConditions:
            financialConditions[fc.consultant_id] = {} # Empty dict for missions
        financialConditions[fc.consultant_id][fc.mission_id] = fc.daily_rate

    # Collect billsData for done work according to timesheet billsData
    for ts in Timesheet.objects.filter(mission__financialcondition__isnull=False).select_related():
        kdate = ts.working_date.replace(day=1)
        if not tsData.has_key(kdate):
            tsData[kdate] = 0 # Create key
        tsData[kdate] += ts.charge * financialConditions.get(ts.consultant_id, {}).get(ts.mission_id, 0) / 1000

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
    # Sort values according to keys
    ydata = sortedValues(tsData)
    # Draw done work
    plots.append(ax.plot(tsKdates, ydata, '--o', ms=5, lw=2, color="blue", mfc="blue"))
    for kdate, ydata in tsData.items():
        ax.text(kdate, ydata + 5, int(ydata))
    # Add Legend and setup axes
    ax.set_xticks(tsKdates)
    ax.set_xticklabels([d.strftime("%b %y") for d in tsKdates])
    ax.set_ylim(ymax=int(max(max(bottom), max(tsData.values()))) + 20)
    ax.set_ylabel(u"k€")
    ax.legend(plots, [i[1] for i in Bill.BILL_STATE] + [_(u"Done work")],
              bbox_to_anchor=(0., 1.02, 1., .102), loc=4,
              ncol=5, borderaxespad=0.)
    ax.grid(True)
    fig.autofmt_xdate()

    return print_png(fig)
