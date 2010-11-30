# coding: utf-8
"""
Pydici billing views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from datetime import date, timedelta

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core import urlresolvers
from django.http import HttpResponseRedirect

from pydici.billing.models import Bill
from pydici.leads.models import Lead

def bill_review(request):
    """Review of bills: bills overdue, due soon, or to be created"""
    today = date.today()
    wait_warning = timedelta(15) # wait in days used to warn that a bill is due soon

    # Get bills overdue, due soon, litigious and recently paid
    overdue_bills = Bill.objects.filter(state="1_SENT").filter(due_date__lte=today)
    soondue_bills = Bill.objects.filter(state="1_SENT").filter(due_date__gt=today).filter(due_date__lte=(today + wait_warning))
    recent_bills = Bill.objects.filter(state="2_PAID").order_by("-payment_date")[:20]
    litigious_bills = Bill.objects.filter(state="3_LITIGIOUS")

    return render_to_response("billing/bill_review.html",
                              {"overdue_bills" : overdue_bills,
                               "soondue_bills" : soondue_bills,
                               "recent_bills" : recent_bills,
                               "litigious_bills" : litigious_bills,
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
