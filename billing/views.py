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
from django.utils.translation import ugettext as _
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.db.models import Sum, Q, F
from django.views.generic import TemplateView
from django.views.decorators.cache import cache_page
from django.forms.models import inlineformset_factory

from django_weasyprint import PDFTemplateView

from billing.utils import get_billing_info, generate_bill_pdf, create_client_bill_from_timesheet, create_client_bill_from_proportion
from billing.models import ClientBill, SupplierBill, BillDetail, BillExpense
from leads.models import Lead
from people.models import Consultant
from staffing.models import Timesheet, FinancialCondition, Staffing, Mission
from crm.models import Subsidiary
from core.utils import get_fiscal_years, get_parameter
from crm.models import Company
from core.utils import COLORS, sortedValues, nextMonth, previousMonth
from core.decorator import pydici_non_public, PydiciNonPublicdMixin, pydici_feature
from billing.forms import BillDetailInlineFormset, BillExpenseFormSetHelper, BillExpenseInlineFormset, BillExpenseForm
from billing.forms import ClientBillForm, BillDetailForm, BillDetailFormSetHelper
import pydici.settings


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

class Bill(PydiciNonPublicdMixin, TemplateView):
    template_name = 'billing/bill.html'

    def get_context_data(self, **kwargs):
        context = super(Bill, self).get_context_data(**kwargs)
        try:
            bill = ClientBill.objects.get(id=kwargs.get("bill_id"))
            context["bill"] = bill
        except ClientBill.DoesNotExist:
            bill = None
        return context


class BillPdf(Bill, PDFTemplateView):
    def get_filename(self):

        bill = self.get_context_data(**self.kwargs)["bill"]
        try:
            filename = u"%s-%s.pdf" % (bill.lead.deal_id, bill.bill_id)
        except ValueError:
            # Incomplete bill, we still want to generate the pdf
            filename = "bill.pdf"
        return filename


def client_bill(request, bill_id=None):
    billDetailFormSet = None
    billExpenseFormSet = None
    if bill_id:
        try:
            bill = ClientBill.objects.get(id=bill_id)
        except ClientBill.DoesNotExist:
            raise Http404
    else:
        bill = None
    BillDetailFormSet = inlineformset_factory(ClientBill, BillDetail, formset=BillDetailInlineFormset, form=BillDetailForm, fields="__all__")
    BillExpenseFormSet = inlineformset_factory(ClientBill, BillExpense, formset=BillExpenseInlineFormset, form=BillExpenseForm, fields="__all__")
    if request.POST:
        form = ClientBillForm(request.POST, request.FILES, instance=bill)
        if bill and bill.state in ("0_DRAFT", "0_PROPOSED"):
            billDetailFormSet = BillDetailFormSet(request.POST, instance=bill)
            billExpenseFormSet = BillExpenseFormSet(request.POST, instance=bill)
        if form.is_valid() and (billDetailFormSet is None or billDetailFormSet.is_valid()) and (billExpenseFormSet is None or billExpenseFormSet.is_valid()):
            bill = form.save()
            if billDetailFormSet:
                billDetailFormSet.save()
            if billExpenseFormSet:
                billExpenseFormSet.save()
            if bill.state in ("0_DRAFT", "0_PROPOSED"):
                success_url = urlresolvers.reverse_lazy("client_bill", args=[bill.id, ])
            else:
                success_url = request.GET.get('return_to', False) or urlresolvers.reverse_lazy("company_detail", args=[bill.lead.client.organisation.company.id, ]) + "#goto_tab-billing"
                if not bill.bill_file:
                    generate_bill_pdf(bill, pydici.settings.MEDIA_ROOT)
            return HttpResponseRedirect(success_url)
    else:
        if bill:
            form = ClientBillForm(instance=bill)
            if bill.state in ("0_DRAFT", "0_PROPOSED"):
                billDetailFormSet = BillDetailFormSet(instance=bill)
                billExpenseFormSet = BillExpenseFormSet(instance=bill)
        else:
            # Still no bill, let's create it with its detail if at least mission has been provided
            if request.GET.get("mission"):
                mission = Mission.objects.get(id=request.GET.get("mission"))
                if mission.billing_mode == "TIME_SPENT":
                    if request.GET.get("month") and request.GET.get("year"):
                        month = date(int(request.GET.get("year")), int(request.GET.get("month")), 1)
                    else:
                        month = date.today().replace(day=1)
                    bill = create_client_bill_from_timesheet(mission, month)
                else: # FIXED_PRICE mission
                    proportion = request.GET.get("proportion", 0.30)
                    bill = create_client_bill_from_proportion(mission, proportion=proportion)

                form = ClientBillForm(instance=bill)
                billDetailFormSet = BillDetailFormSet(instance=bill)
                billExpenseFormSet = BillExpenseFormSet(instance=bill)
            else:
                form = ClientBillForm()
    return render(request, "billing/bill_form.html",
                  {"bill_form": form,
                   "detail_formset": billDetailFormSet,
                   "detail_formset_helper": BillDetailFormSetHelper(),
                   "expense_formset": billExpenseFormSet,
                   "expense_formset_helper": BillExpenseFormSetHelper(),
                   "bill_id": bill.id if bill else None,
                   "user": request.user})


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
    internalBilling = {}  # Same structure as timeSpentBilling but for billing between internal subsidiaries

    try:
        billing_consultant = Consultant.objects.get(trigramme__iexact=request.user.username)
    except Consultant.DoesNotExist:
        billing_consultant = None
        mine = False


    fixedPriceMissions = Mission.objects.filter(nature="PROD", billing_mode="FIXED_PRICE",
                                                timesheet__working_date__gte=month,
                                                timesheet__working_date__lt=next_month)
    undefinedBillingModeMissions = Mission.objects.filter(nature="PROD", billing_mode=None,
                                                          timesheet__working_date__gte=month,
                                                          timesheet__working_date__lt=next_month)

    timespent_timesheets = Timesheet.objects.filter(working_date__gte=month, working_date__lt=next_month,
                                                    mission__nature="PROD", mission__billing_mode="TIME_SPENT")

    internalBillingTimesheets = Timesheet.objects.filter(working_date__gte=month, working_date__lt=next_month,
                                                    mission__nature="PROD")
    internalBillingTimesheets = internalBillingTimesheets.exclude(Q(consultant__company=F("mission__subsidiary")) & Q(consultant__company=F("mission__lead__subsidiary")))
    #TODO: hanlde fixed price mission fully delegated to a subsidiary

    if mine:  # Filter on consultant mission/lead as responsible
        fixedPriceMissions = fixedPriceMissions.filter(Q(lead__responsible=billing_consultant) | Q(responsible=billing_consultant))
        undefinedBillingModeMissions = undefinedBillingModeMissions.filter(Q(lead__responsible=billing_consultant) | Q(responsible=billing_consultant))
        timespent_timesheets = timespent_timesheets.filter(Q(mission__lead__responsible=billing_consultant) | Q(mission__responsible=billing_consultant))
        internalBillingTimesheets = internalBillingTimesheets.filter(Q(mission__lead__responsible=billing_consultant) | Q(mission__responsible=billing_consultant))

    fixedPriceMissions = fixedPriceMissions.order_by("lead").distinct()
    undefinedBillingModeMissions = undefinedBillingModeMissions.order_by("lead").distinct()

    timesheet_data = timespent_timesheets.order_by("mission__lead", "consultant").values_list("mission", "consultant").annotate(Sum("charge"))
    timeSpentBilling = get_billing_info(timesheet_data)

    for subsidiary in Subsidiary.objects.all():
        subsidiary_timesheet_data = internalBillingTimesheets.filter(consultant__company=subsidiary)
        for target_subsidiary in Subsidiary.objects.exclude(pk=subsidiary.id):
            timesheet_data = subsidiary_timesheet_data.filter(mission__lead__subsidiary=target_subsidiary)
            timesheet_data = timesheet_data .order_by("mission__lead", "consultant").values_list("mission", "consultant").annotate(Sum("charge"))
            billing_info = get_billing_info(timesheet_data)
            if billing_info:
                internalBilling[(subsidiary,target_subsidiary)] = billing_info

    return render(request, "billing/pre_billing.html",
                  {"time_spent_billing": timeSpentBilling,
                   "fixed_price_missions": fixedPriceMissions,
                   "undefined_billing_mode_missions": undefinedBillingModeMissions,
                   "internal_billing": internalBilling,
                   "month": month,
                   "mine": mine,
                   "user": request.user})


@pydici_non_public
def client_bills_in_creation(request):
    """Review client bill in preparation"""
    return render(request, "billing/client_bills_in_creation.html",
                  {"data_url": urlresolvers.reverse('client_bills_in_creation_DT'),
                   "user": request.user})


@pydici_non_public
def client_bills_archive(request):
    """Review all client bill """
    return render(request, "billing/client_bills_archive.html",
                  {"data_url": urlresolvers.reverse('client_bills_archive'),
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
    bills = ClientBill.objects.filter(creation_date__gt=start_date, state__in=("1_SENT", "2_PAID"))
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
        staffingData[kdate] += staffing.charge * financialConditions.get(staffing.consultant_id, {}).get(staffing.mission_id, 0) / 1000
        wStaffingData[kdate] += staffing.charge * financialConditions.get(staffing.consultant_id, {}).get(staffing.mission_id, 0) * staffing.mission.probability / 100 / 1000

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


@pydici_non_public
@pydici_feature("reports")
@cache_page(60 * 10)
def graph_yearly_billing(request):
    """Fiscal year billing per subsidiary"""
    bills = ClientBill.objects.filter(state__in=("1_SENT", "2_PAID"))
    years = get_fiscal_years(bills, "creation_date")
    month = int(get_parameter("FISCAL_YEAR_MONTH"))
    data = {}
    graph_data = []
    labels = []
    growth = []
    subsidiaries = Subsidiary.objects.all()
    for subsidiary in subsidiaries:
        data[subsidiary.name] = []

    for year in years:
        turnover = {}
        for subsidiary_name, amount in bills.filter(creation_date__gte=date(year, month, 1), creation_date__lt=date(year + 1, month, 1)).values_list("lead__subsidiary__name").annotate(Sum("amount")):
            turnover[subsidiary_name] = float(amount)
        for subsidiary in subsidiaries:
            data[subsidiary.name].append(turnover.get(subsidiary.name, 0))

    last_turnover = 0
    for current_turnover in [sum(i) for i in zip(*data.values())]:  # Total per year
        if last_turnover > 0:
            growth.append(round(100 * (current_turnover - last_turnover) / last_turnover, 1))
        else:
            growth.append(None)
        last_turnover = current_turnover

    if years[-1] == date.today().year:
        growth.pop()  # Don't compute for on-going year.

    graph_data.append(["x"] + years)  # X (years) axis

    # Add turnover per subsidiary
    for key, value in data.items():
        if sum(value) == 0:
            continue
        value.insert(0, key)
        graph_data.append(value)
        labels.append(key)

    # Add growth
    graph_data.append([_("growth")] + growth)
    labels.append(_("growth"))

    return render(request, "billing/graph_yearly_billing.html",
                  {"graph_data": json.dumps(graph_data),
                   "years": years,
                   "subsidiaries" : json.dumps(labels),
                   "series_colors": COLORS,
                   "user": request.user})
