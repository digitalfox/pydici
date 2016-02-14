# coding: utf-8
"""
Pydici billing views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta
import mimetypes
from collections import defaultdict
import json


from django.shortcuts import render
from django.core import urlresolvers
from django.http import HttpResponseRedirect, HttpResponse
from django.db.models import Sum, Q
from django.views.decorators.cache import cache_page

from billing.models import ClientBill, SupplierBill
from leads.models import Lead
from people.models import Consultant
from staffing.models import Timesheet, FinancialCondition, Staffing, Mission
from staffing.utils import gatherTimesheetData
from crm.models import Company
from core.utils import COLORS, sortedValues, nextMonth, previousMonth, to_int_or_round, working_days
from staffing.utils import holidayDays
from core.decorator import pydici_non_public, pydici_feature


@pydici_non_public
@pydici_feature("reports")
def bill_review(request):
    """Review of bills: bills overdue, due soon, or to be created"""
    today = date.today()
    wait_warning = timedelta(15)  # wait in days used to warn that a bill is due soon

    # Get bills overdue, due soon, litigious and recently paid
    overdue_bills = ClientBill.objects.filter(state="1_SENT").filter(due_date__lte=today).select_related()
    soondue_bills = ClientBill.objects.filter(state="1_SENT").filter(due_date__gt=today).filter(due_date__lte=(today + wait_warning)).select_related()
    recent_bills = ClientBill.objects.filter(state="2_PAID").order_by("-payment_date").select_related()[:20]
    litigious_bills = ClientBill.objects.filter(state="3_LITIGIOUS").select_related()

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
        if lead.clientbill_set.count() == 0:
            if Timesheet.objects.filter(mission__lead=lead, working_date__gte=threeMonthAgo).count() != 0:
                leadsWithoutBill.append(lead)

    return render(request, "billing/bill_review.html",
                  {"overdue_bills": overdue_bills,
                   "soondue_bills": soondue_bills,
                   "recent_bills": recent_bills,
                   "litigious_bills": litigious_bills,
                   "soondue_bills_total": soondue_bills_total,
                   "overdue_bills_total": overdue_bills_total,
                   "litigious_bills_total": litigious_bills_total,
                   "soondue_bills_total_with_vat": soondue_bills_total_with_vat,
                   "overdue_bills_total_with_vat": overdue_bills_total_with_vat,
                   "litigious_bills_total_with_vat": litigious_bills_total_with_vat,
                   "leads_without_bill": leadsWithoutBill,
                   "user": request.user})


@pydici_non_public
@pydici_feature("reports")
def bill_payment_delay(request):
    """Report on client bill payment delay"""
    # List of tuple (company, avg delay in days)
    directDelays = list()  # for direct client
    indirectDelays = list()  # for client with paying authority
    for company in Company.objects.all():
        # Direct delays
        bills = ClientBill.objects.filter(lead__client__organisation__company=company, lead__paying_authority__isnull=True, state="2_PAID")
        res = [i.payment_delay() for i in bills]
        if res:
            directDelays.append((company, sum(res) / len(res)))
        # Indirect delays
        bills = ClientBill.objects.filter(lead__paying_authority__company=company, state="2_PAID")
        res = [i.payment_delay() for i in bills]
        if res:
            indirectDelays.append((company, sum(res) / len(res)))

    return render(request, "billing/payment_delay.html",
                  {"direct_delays": directDelays,
                   "indirect_delays": indirectDelays,
                   "user": request.user},)


@pydici_non_public
@pydici_feature("management")
def mark_bill_paid(request, bill_id):
    """Mark the given bill as paid"""
    bill = ClientBill.objects.get(id=bill_id)
    bill.state = "2_PAID"
    bill.save()
    return HttpResponseRedirect(urlresolvers.reverse("billing.views.bill_review"))


@pydici_non_public
@pydici_feature("management")
def bill_file(request, bill_id=0, nature="client"):
    """Returns bill file"""
    response = HttpResponse()
    try:
        if nature == "client":
            bill = ClientBill.objects.get(id=bill_id)
        else:
            bill = SupplierBill.objects.get(id=bill_id)
        if bill.bill_file:
            response['Content-Type'] = mimetypes.guess_type(bill.bill_file.name)[0] or "application/stream"
            for chunk in bill.bill_file.chunks():
                response.write(chunk)
    except (ClientBill.DoesNotExist, SupplierBill.DoesNotExist, OSError):
        pass

    return response


@pydici_non_public
@pydici_feature("management")
def pre_billing(request, year=None, month=None, mine=False):
    """Pre billing page: help to identify bills to send"""
    if year and month:
        month = date(int(year), int(month), 1)
    else:
        month = previousMonth(date.today())

    next_month = nextMonth(month)
    timeSpentBilling = {}  # Key is lead, value is total and dict of mission(total, Mission billingData)
    rates = {}  # Key is mission, value is Consultant rates dict

    try:
        billing_consultant = Consultant.objects.get(trigramme__iexact=request.user.username)
    except Consultant.DoesNotExist:
        billing_consultant = None
        mine = False

    # Check consultant timesheet to hint if billing could be done based on a clean state
    timesheet_ok = {}
    for consultant in Consultant.objects.filter(active=True, subcontractor=False):
        missions = consultant.timesheet_missions(month=month)
        timesheetData, timesheetTotal, warning = gatherTimesheetData(consultant, missions, month)
        days = sum([v for (k,v) in timesheetTotal.items() if k!="ticket"])  # Compute timesheet days. Remove lunch ticket count
        if days == working_days(month, holidayDays(month=month)):
            timesheet_ok[consultant.id] = True
        else:
            timesheet_ok[consultant.id] = False

    fixedPriceMissions = Mission.objects.filter(nature="PROD", billing_mode="FIXED_PRICE",
                                                timesheet__working_date__gte=month,
                                                timesheet__working_date__lt=next_month)
    undefinedBillingModeMissions = Mission.objects.filter(nature="PROD", billing_mode=None,
                                                          timesheet__working_date__gte=month,
                                                          timesheet__working_date__lt=next_month)
    if mine:
        fixedPriceMissions = fixedPriceMissions.filter(Q(lead__responsible=billing_consultant) | Q(responsible=billing_consultant))
        undefinedBillingModeMissions = undefinedBillingModeMissions.filter(Q(lead__responsible=billing_consultant) | Q(responsible=billing_consultant))

    fixedPriceMissions = fixedPriceMissions.order_by("lead").distinct()
    undefinedBillingModeMissions = undefinedBillingModeMissions.order_by("lead").distinct()

    timesheets = Timesheet.objects.filter(working_date__gte=month, working_date__lt=next_month,
                                          mission__nature="PROD", mission__billing_mode="TIME_SPENT")
    if mine:
        timesheets = timesheets.filter(Q(mission__lead__responsible=billing_consultant) | Q(mission__responsible=billing_consultant))
    timesheet_data = timesheets.order_by("mission__lead", "consultant").values_list("mission", "consultant").annotate(Sum("charge"))
    for mission_id, consultant_id, charge in timesheet_data:
        mission = Mission.objects.select_related("lead").get(id=mission_id)
        if mission.lead:
            lead = mission.lead
        else:
            # Bad data, mission with nature prod without lead... This should not happened
            continue
        consultant = Consultant.objects.get(id=consultant_id)
        if not mission in rates:
            rates[mission] = mission.consultant_rates()
        if not lead in timeSpentBilling:
            timeSpentBilling[lead] = [0.0, {}]  # Lead Total and dict of mission
        if not mission in timeSpentBilling[lead][1]:
            timeSpentBilling[lead][1][mission] = [0.0, []]  # Mission Total and detail per consultant
        total = charge * rates[mission][consultant][0]
        timeSpentBilling[lead][0] += total
        timeSpentBilling[lead][1][mission][0] += total
        timeSpentBilling[lead][1][mission][1].append([consultant, to_int_or_round(charge, 2), rates[mission][consultant][0], total, timesheet_ok.get(consultant_id, True)])

    # Sort data
    timeSpentBilling = timeSpentBilling.items()
    timeSpentBilling.sort(key=lambda x: x[0].deal_id)

    return render(request, "billing/pre_billing.html",
                  {"time_spent_billing": timeSpentBilling,
                   "fixed_price_missions": fixedPriceMissions,
                   "undefined_billing_mode_missions": undefinedBillingModeMissions,
                   "month": month,
                   "mine": mine,
                   "user": request.user})


@pydici_non_public
@pydici_feature("reports")
@cache_page(60 * 10)
def graph_billing_jqp(request):
    """Nice graph bar of incomming cash from bills
    @todo: per year, with start-end date"""
    billsData = defaultdict(list)  # Bill graph Data
    tsData = {}  # Timesheet done work graph data
    staffingData = {}  # Staffing forecasted work graph data
    wStaffingData = {}  # Weighted Staffing forecasted work graph data
    today = date.today()
    start_date = today - timedelta(24 * 30)  # Screen data about 24 month before today
    end_date = today + timedelta(6 * 30)  # No more than 6 month forecasted
    graph_data = []  # Data that will be returned to jqplot

    # Gathering billsData
    bills = ClientBill.objects.filter(creation_date__gt=start_date)
    if bills.count() == 0:
        return HttpResponse()

    for bill in bills:
        # Using first day of each month as key date
        kdate = bill.creation_date.replace(day=1)
        billsData[kdate].append(bill)

    # Collect Financial conditions as a hash for further lookup
    financialConditions = {}  # First key is consultant id, second is mission id. Value is daily rate
    # TODO: filter FC on timesheet date to forget old fc (perf)
    for fc in FinancialCondition.objects.filter(mission__nature="PROD"):
        if not fc.consultant_id in financialConditions:
            financialConditions[fc.consultant_id] = {}  # Empty dict for missions
        financialConditions[fc.consultant_id][fc.mission_id] = fc.daily_rate

    # Collect data for done work according to timesheet data
    for ts in Timesheet.objects.filter(working_date__lt=today, working_date__gt=start_date, mission__nature="PROD").select_related():
        kdate = ts.working_date.replace(day=1)
        if kdate not in tsData:
            tsData[kdate] = 0  # Create key
        tsData[kdate] += ts.charge * financialConditions.get(ts.consultant_id, {}).get(ts.mission_id, 0) / 1000

    # Collect data for forecasted work according to staffing data
    for staffing in Staffing.objects.filter(staffing_date__gte=today.replace(day=1), staffing_date__lt=end_date, mission__nature="PROD").select_related():
        kdate = staffing.staffing_date.replace(day=1)
        if kdate not in staffingData:
            staffingData[kdate] = 0  # Create key
            wStaffingData[kdate] = 0  # Create key
        staffingData[kdate] += staffing.charge * financialConditions.get(ts.consultant_id, {}).get(ts.mission_id, 0) / 1000
        wStaffingData[kdate] += staffing.charge * financialConditions.get(ts.consultant_id, {}).get(ts.mission_id, 0) * staffing.mission.probability / 100 / 1000

    # Set bottom of each graph. Starts if [0, 0, 0, ...]
    billKdates = billsData.keys()
    billKdates.sort()
    isoBillKdates = [a.isoformat() for a in billKdates]  # List of date as string in ISO format

    # Draw a bar for each state
    for state in ClientBill.CLIENT_BILL_STATE:
        ydata = [sum([float(i.amount) / 1000 for i in x if i.state == state[0]]) for x in sortedValues(billsData)]
        graph_data.append(zip(isoBillKdates, ydata))

    # Sort keys
    tsKdates = tsData.keys()
    tsKdates.sort()
    isoTsKdates = [a.isoformat() for a in tsKdates]  # List of date as string in ISO format
    staffingKdates = staffingData.keys()
    staffingKdates.sort()
    isoStaffingKdates = [a.isoformat() for a in staffingKdates]  # List of date as string in ISO format
    wStaffingKdates = staffingData.keys()
    wStaffingKdates.sort()
    isoWstaffingKdates = [a.isoformat() for a in wStaffingKdates]  # List of date as string in ISO format

    # Sort values according to keys
    tsYData = sortedValues(tsData)
    staffingYData = sortedValues(staffingData)
    wStaffingYData = sortedValues(wStaffingData)

    # Draw done work
    graph_data.append(zip(isoTsKdates, tsYData))

    # Draw forecasted work
    graph_data.append(zip(isoStaffingKdates, staffingYData))
    graph_data.append(zip(isoWstaffingKdates, wStaffingYData))

    return render(request, "billing/graph_billing_jqp.html",
                  {"graph_data": json.dumps(graph_data),
                   "series_label": [i[1] for i in ClientBill.CLIENT_BILL_STATE],
                   "series_colors": COLORS,
                   # "min_date": min_date,
                   "user": request.user})
