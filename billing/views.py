# coding: utf-8
"""
Pydici billing views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from datetime import date, timedelta
import itertools

from matplotlib.figure import Figure

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core import urlresolvers
from django.http import HttpResponseRedirect
from django.db.models import Sum

from pydici.billing.models import Bill
from pydici.leads.models import Lead
from pydici.staffing.models import Timesheet
from pydici.crm.models import ClientCompany, BusinessBroker
from pydici.core.utils import print_png, COLORS

def bill_review(request):
    """Review of bills: bills overdue, due soon, or to be created"""
    today = date.today()
    wait_warning = timedelta(15) # wait in days used to warn that a bill is due soon

    # Get bills overdue, due soon, litigious and recently paid
    overdue_bills = Bill.objects.filter(state="1_SENT").filter(due_date__lte=today)
    soondue_bills = Bill.objects.filter(state="1_SENT").filter(due_date__gt=today).filter(due_date__lte=(today + wait_warning))
    recent_bills = Bill.objects.filter(state="2_PAID").order_by("-payment_date")[:20]
    litigious_bills = Bill.objects.filter(state="3_LITIGIOUS")

    # Compute totals
    soondue_bills_total = soondue_bills.aggregate(Sum("amount"))["amount__sum"]
    overdue_bills_total = overdue_bills.aggregate(Sum("amount"))["amount__sum"]
    litigious_bills_total = litigious_bills.aggregate(Sum("amount"))["amount__sum"]

    # Get leads with done timesheet in past three month that don't have bill yet
    leadsWithoutBill = []
    threeMonthAgo = date.today() - timedelta(90)
    for lead in Lead.objects.filter(state="WON"):
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
    data = {} # Graph data
    bars = [] # List of bars - needed to add legend
    colors = itertools.cycle(COLORS)

    # Setting up graph
    fig = Figure(figsize=(12, 8))
    fig.set_facecolor("white")
    ax = fig.add_subplot(111)

    # Gathering data
    bills = Bill.objects.all()
    if bills.count() == 0:
        return print_png(fig)

    for bill in bills:
        #Using first day of each month as key date
        kdate = date(bill.creation_date.year, bill.creation_date.month, 1)
        if not data.has_key(kdate):
            data[kdate] = [] # Create key with empty list
        data[kdate].append(bill)

    # Set bottom of each graph. Starts if [0, 0, 0, ...]
    bottom = [0] * len(data.keys())

    # Draw a bar for each state
    for state in Bill.BILL_STATE:
        ydata = [sum([i.amount for i in x if i.state == state[0]]) for x in data.values()]
        b = ax.bar(data.keys(), ydata, bottom=bottom, align="center", width=15,
               color=colors.next())
        bars.append(b[0])
        for i in range(len(ydata)):
            bottom[i] += ydata[i] # Update bottom

    # Add Legend and setup axes
    ax.set_xticks(data.keys())
    ax.set_xticklabels(data.keys())
    ax.set_ylim(ymax=int(max(bottom)) + 10)
    ax.legend(bars, [i[1] for i in Bill.BILL_STATE],
              bbox_to_anchor=(0., 1.02, 1., .102), loc=4,
              ncol=4, borderaxespad=0.)
    ax.grid(True)
    fig.autofmt_xdate()

    return print_png(fig)
