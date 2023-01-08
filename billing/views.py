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
from io import BytesIO
import os
import subprocess
import tempfile

from os.path import basename

from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.utils import translation
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.db.models import Sum, Q, F, Min, Max, Count
from django.views.generic import TemplateView
from django.views.decorators.cache import cache_page
from django.forms.models import inlineformset_factory
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.template.loader import get_template


from django_weasyprint.views import WeasyTemplateResponse, WeasyTemplateView
from PyPDF2 import PdfFileMerger, PdfFileReader
import facturx

from billing.utils import get_billing_info, update_client_bill_from_timesheet, update_client_bill_from_proportion, \
    bill_pdf_filename, get_client_billing_control_pivotable_data, generate_bill_pdf
from billing.models import ClientBill, SupplierBill, BillDetail, BillExpense
from leads.models import Lead
from people.models import Consultant
from staffing.models import Timesheet, FinancialCondition, Staffing, Mission
from staffing.views import MissionTimesheetReportPdf
from crm.models import Subsidiary
from crm.utils import get_subsidiary_from_session
from core.utils import get_fiscal_years_from_qs, get_parameter, user_has_feature
from core.utils import COLORS, sortedValues, nextMonth, previousMonth
from core.decorator import pydici_non_public, PydiciNonPublicdMixin, pydici_feature, PydiciFeatureMixin
from billing.forms import BillDetailInlineFormset, BillExpenseFormSetHelper, BillExpenseInlineFormset, BillExpenseForm
from billing.forms import ClientBillForm, BillDetailForm, BillDetailFormSetHelper, SupplierBillForm


@pydici_non_public
@pydici_feature("reports")
def bill_review(request):
    """Review of bills: bills overdue, due soon, or to be created"""
    today = date.today()
    wait_warning = timedelta(15)  # wait in days used to warn that a bill is due soon

    subsidiary = get_subsidiary_from_session(request)

    # Get bills overdue, due soon, litigious and recently paid
    overdue_bills = ClientBill.objects.filter(state="1_SENT", due_date__lte=today).select_related()
    soondue_bills = ClientBill.objects.filter(state="1_SENT", due_date__gt=today, due_date__lte=(today + wait_warning)).select_related()
    recent_bills = ClientBill.objects.filter(state="2_PAID").order_by("-payment_date").select_related()
    litigious_bills = ClientBill.objects.filter(state="3_LITIGIOUS").select_related()
    supplier_overdue_bills = SupplierBill.objects.filter(state__in=("1_RECEIVED", "1_VALIDATED"), due_date__lte=today).select_related()
    supplier_soondue_bills = SupplierBill.objects.filter(state__in=("1_RECEIVED", "1_VALIDATED"), due_date__gt=today).select_related()

    # Filter bills on subsidiary if defined
    if subsidiary:
        overdue_bills = overdue_bills.filter(lead__subsidiary=subsidiary)
        soondue_bills = soondue_bills.filter(lead__subsidiary=subsidiary)
        recent_bills = recent_bills.filter(lead__subsidiary=subsidiary)
        litigious_bills = litigious_bills.filter(lead__subsidiary=subsidiary)
        supplier_overdue_bills = supplier_overdue_bills.filter(lead__subsidiary=subsidiary)
        supplier_soondue_bills = supplier_soondue_bills.filter(lead__subsidiary=subsidiary)

    # Limit recent bill to last 20 ones
    recent_bills = recent_bills[: 20]

    # Compute totals
    soondue_bills_total = soondue_bills.aggregate(Sum("amount"))["amount__sum"]
    overdue_bills_total = overdue_bills.aggregate(Sum("amount"))["amount__sum"]
    litigious_bills_total = litigious_bills.aggregate(Sum("amount"))["amount__sum"]
    soondue_bills_total_with_vat = sum([bill.amount_with_vat for bill in soondue_bills if bill.amount_with_vat])
    overdue_bills_total_with_vat = sum([bill.amount_with_vat for bill in overdue_bills if bill.amount_with_vat])
    litigious_bills_total_with_vat = sum([bill.amount_with_vat for bill in litigious_bills if bill.amount_with_vat])

    # Get leads with done timesheet in past three month that don't have bill yet
    leads_without_bill = Lead.objects.filter(state="WON", mission__timesheet__working_date__gte=(date.today() - timedelta(90)))
    leads_without_bill = leads_without_bill.annotate(Count("clientbill")).filter(clientbill__count=0)
    if subsidiary:
        leads_without_bill = leads_without_bill.filter(subsidiary=subsidiary)

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
                   "leads_without_bill": leads_without_bill,
                   "supplier_soondue_bills": supplier_soondue_bills,
                   "supplier_overdue_bills": supplier_overdue_bills,
                   "billing_management": user_has_feature(request.user, "billing_management"),
                   "consultant": Consultant.objects.filter(trigramme__iexact=request.user.username).first(),
                   "user": request.user})


@pydici_non_public
@pydici_feature("reports")
@cache_page(60 * 60 * 24)
def bill_delay(request):
    """Report on client bill creation and payment delay"""
    data = []
    subsidiary = get_subsidiary_from_session(request)
    bills = ClientBill.objects.filter(creation_date__gt=(date.today() - timedelta(2*365)), state__in=("1_SENT", "2_PAID"),
                                      amount__gt=0)
    if subsidiary:
        bills = bills.filter(lead__subsidiary=subsidiary)
    bills = bills.select_related("lead__responsible", "lead__subsidiary", "lead__client__organisation__company",
                                 "lead__paying_authority__company", "lead__paying_authority__contact")
    bills = bills.prefetch_related("billdetail_set__mission")
    for bill in bills:
        data.append(
            {_("Lead"): bill.lead.deal_id,
             _("Responsible"): bill.lead.responsible.name,
             _("Subsidiary"): bill.lead.subsidiary.name,
             _("client company"): bill.lead.client.organisation.company.name,
             _("Paying authority"): str(bill.lead.paying_authority or "null"),
             _("Billing mode"): ",".join(list(set([d.mission.get_billing_mode_display() or "NA" for d in bill.billdetail_set.all()] or ["NA"]))),
             _("creation lag"): bill.creation_lag() or "null",
             _("payment delay"): bill.payment_delay(),
             _("payment wait"): bill.payment_wait(),
             _("creation date"): bill.creation_date.replace(day=1).isoformat()}
        )
    return render(request, "billing/payment_delay.html",
                  {"data": data,
                   "user": request.user},)


class BillingRequestMixin(PydiciFeatureMixin):
    pydici_feature = "billing_request"


@pydici_non_public
@pydici_feature("billing_management")
def mark_bill_paid(request, bill_id):
    """Mark the given bill as paid"""
    bill = ClientBill.objects.get(id=bill_id)
    bill.state = "2_PAID"
    bill.save()
    return HttpResponseRedirect(reverse("billing:bill_review"))


@pydici_non_public
@pydici_feature("management")
def validate_supplier_bill(request, bill_id):
    """Mark the given supplier bill as validated"""
    consultant = Consultant.objects.filter(trigramme__iexact=request.user.username).first()
    bill = SupplierBill.objects.get(id=bill_id)
    if consultant == bill.lead.responsible and bill.state == "1_RECEIVED":
        bill.state = "1_VALIDATED"
        bill.save()
        return HttpResponseRedirect(reverse("billing:bill_review"))
    else:
        return HttpResponseRedirect(reverse("core:forbidden"))


@pydici_non_public
@pydici_feature("billing_management")
def mark_supplierbill_paid(request, bill_id):
    """Mark the given supplier bill as paid"""
    bill = SupplierBill.objects.get(id=bill_id)
    bill.state = "2_PAID"
    bill.save()
    return HttpResponseRedirect(reverse("billing:bill_review"))


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
            response["Content-Type"] = mimetypes.guess_type(bill.bill_file.name)[0] or "application/stream"
            response["Content-Disposition"] = 'attachment; filename="%s"' % basename(bill.bill_file.name)
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
            context["expenses_image_receipt"] = []
            for expenseDetail in bill.billexpense_set.all():
                if expenseDetail.expense and expenseDetail.expense.receipt_content_type() != "application/pdf":
                    context["expenses_image_receipt"].append(expenseDetail.expense.receipt_data())
        except ClientBill.DoesNotExist:
            bill = None
        return context

    @method_decorator(pydici_feature("billing_request"))
    def dispatch(self, *args, **kwargs):
        return super(Bill, self).dispatch(*args, **kwargs)


class BillAnnexPDFTemplateResponse(WeasyTemplateResponse):
    """TemplateResponse override to merge """
    @property
    def rendered_content(self):
        old_lang = translation.get_language()
        try:
            target = BytesIO()
            bill = self.context_data["bill"]
            translation.activate(bill.lang)
            bill_pdf = super(BillAnnexPDFTemplateResponse, self).rendered_content
            merger = PdfFileMerger()
            merger.append(PdfFileReader(BytesIO(bill_pdf)))
            # Add expense receipt
            for billExpense in bill.billexpense_set.all():
                if billExpense.expense and billExpense.expense.receipt_content_type() == "application/pdf":
                    merger.append(PdfFileReader(billExpense.expense.receipt.file))
            # Add timesheet
            if bill.include_timesheet:
                fake_http_request = self._request
                fake_http_request.method = "GET"
                for mission in Mission.objects.filter(billdetail__bill=bill).annotate(Min("billdetail__month"), Max("billdetail__month")).distinct():
                    response = MissionTimesheetReportPdf.as_view()(fake_http_request, mission=mission,
                                                                   start=mission.billdetail__month__min,
                                                                   end=mission.billdetail__month__max)
                    merger.append(BytesIO(response.rendered_content))
            merger.write(target)
            target.seek(0)  # Be kind, rewind
            # Make it PDF/A-3B compliant
            cmd = "gs -q -dPDFA=3 -dBATCH -dNOPAUSE -sColorConversionStrategy=UseDeviceIndependentColor -sDEVICE=pdfwrite -dPDFACompatibilityPolicy=1 -sOutputFile=- -"
            try:
                gs_in = tempfile.TemporaryFile()
                gs_out = tempfile.TemporaryFile()
                gs_in.write(target.getvalue())
                target.close()
                gs_in.seek(0)
                subprocess.run(cmd.split(), stdin=gs_in, stdout=gs_out)
                gs_out.seek(0)
                # Add factur-x information
                facturx_xml = get_template("billing/invoice-factur-x.xml").render({"bill": bill})
                facturx_xml = facturx_xml.encode("utf-8")
                pdf_metadata = {
                    "author": "enioka",
                    "keywords": "Factur-X, Invoice, pydici",
                    "title": "enioka Invoice %s" % bill.bill_id,
                    "subject": "Factur-X invoice %s dated %s issued by enioka" % (bill.bill_id, bill.creation_date),
                }
                facturx_pdf = facturx.generate_from_binary(gs_out.read(), facturx_xml, pdf_metadata=pdf_metadata, lang=bill.lang)
            finally:
                gs_out.close()
                gs_in.close()
        finally:
            translation.activate(old_lang)
        return facturx_pdf


class BillPdf(Bill, WeasyTemplateView):
    response_class = BillAnnexPDFTemplateResponse

    def get_filename(self):
        bill = self.get_context_data(**self.kwargs)["bill"]
        return bill_pdf_filename(bill)


@pydici_non_public
@pydici_feature("billing_request")
def client_bill(request, bill_id=None):
    """Add or edit client bill"""
    billDetailFormSet = None
    billExpenseFormSet = None
    billing_management_feature = "billing_management"
    forbidden = HttpResponseRedirect(reverse("core:forbidden"))
    if bill_id:
        try:
            bill = ClientBill.objects.get(id=bill_id)
        except ClientBill.DoesNotExist:
            raise Http404
    else:
        bill = None
    BillDetailFormSet = inlineformset_factory(ClientBill, BillDetail, formset=BillDetailInlineFormset, form=BillDetailForm, fields="__all__")
    BillExpenseFormSet = inlineformset_factory(ClientBill, BillExpense, formset=BillExpenseInlineFormset, form=BillExpenseForm, fields="__all__")
    wip_status = ("0_DRAFT", "0_PROPOSED")
    if request.POST:
        form = ClientBillForm(request.POST, request.FILES, instance=bill)
        # First, ensure user is allowed to manipulate the bill
        if bill and bill.state not in wip_status and not user_has_feature(request.user, billing_management_feature):
            return forbidden
        if form.data["state"] not in wip_status and not user_has_feature(request.user, billing_management_feature):
            return forbidden
        # Now, process form
        if bill and bill.state in wip_status:
            billDetailFormSet = BillDetailFormSet(request.POST, instance=bill)
            billExpenseFormSet = BillExpenseFormSet(request.POST, instance=bill)
        if form.is_valid() and (billDetailFormSet is None or billDetailFormSet.is_valid()) and (billExpenseFormSet is None or billExpenseFormSet.is_valid()):
            bill = form.save()
            if billDetailFormSet:
                billDetailFormSet.save()
            if billExpenseFormSet:
                billExpenseFormSet.save()
            bill.save()  # Again, to take into account modified details.
            if bill.state in wip_status:
                success_url = reverse_lazy("billing:client_bill", args=[bill.id, ])
            else:
                success_url = request.GET.get('return_to', False) or reverse_lazy("billing:client_bill_detail", args=[bill.id, ])
                if bill.bill_file:
                    if form.changed_data == ["state"] and billDetailFormSet is None and billExpenseFormSet is None:
                        # only state has change. No need to regenerate bill file.
                        messages.add_message(request, messages.INFO, _("Bill state has been updated"))
                    elif "bill_file" in form.changed_data:
                        # a file has been provided by user himself. We must not generate a file and overwrite it.
                        messages.add_message(request, messages.WARNING, _("Using custom user file to replace current bill"))
                    elif bill.billexpense_set.exists() or bill.billdetail_set.exists():
                        # bill file exist but authorized admin change information and do not provide custom file. Let's generate again bill file
                        messages.add_message(request, messages.WARNING, _("A new bill is generated and replace the previous one"))
                        if os.path.exists(bill.bill_file.path):
                            os.remove(bill.bill_file.path)
                        generate_bill_pdf(bill, request)
                else:
                    # Bill file still not exist. Let's create it
                    messages.add_message(request, messages.INFO, _("A new bill file has been generated"))
                    generate_bill_pdf(bill, request)
            return HttpResponseRedirect(success_url)
    else:
        if bill:
            # Create a form to edit the given bill
            form = ClientBillForm(instance=bill)
            if bill.state in wip_status:
                billDetailFormSet = BillDetailFormSet(instance=bill)
                billExpenseFormSet = BillExpenseFormSet(instance=bill)
        else:
            # Still no bill, let's create it with its detail if at least mission or lead has been provided
            missions = []
            if request.GET.get("lead"):
                lead = Lead.objects.get(id=request.GET.get("lead"))
                missions = lead.mission_set.all()  # take all missions
            if request.GET.get("mission"):
                missions = [Mission.objects.get(id=request.GET.get("mission"))]
            if missions:
                bill = ClientBill.objects.create(lead=missions[0].lead)
                bill.save()
            for mission in missions:
                if mission.billing_mode == "TIME_SPENT":
                    if request.GET.get("start_date") and request.GET.get("end_date"):
                        start_date = date(int(request.GET.get("start_date")[0:4]), int(request.GET.get("start_date")[4:6]), 1)
                        end_date = date(int(request.GET.get("end_date")[0:4]), int(request.GET.get("end_date")[4:6]), 1)
                    else:
                        start_date = previousMonth(date.today())
                        end_date = date.today().replace(day=1)
                    update_client_bill_from_timesheet(bill, mission, start_date, end_date)
                else: # FIXED_PRICE mission
                    proportion = request.GET.get("proportion", 0.30)
                    bill = update_client_bill_from_proportion(bill, mission, proportion=proportion)

            if bill:
                form = ClientBillForm(instance=bill)
                billDetailFormSet = BillDetailFormSet(instance=bill)
                billExpenseFormSet = BillExpenseFormSet(instance=bill)
            else:
                # Simple virgin new form
                form = ClientBillForm()
    return render(request, "billing/client_bill_form.html",
                  {"bill_form": form,
                   "detail_formset": billDetailFormSet,
                   "detail_formset_helper": BillDetailFormSetHelper(),
                   "expense_formset": billExpenseFormSet,
                   "expense_formset_helper": BillExpenseFormSetHelper(),
                   "bill_id": bill.id if bill else None,
                   "can_delete": bill.state in wip_status if bill else False,
                   "can_preview": bill.state in wip_status if bill else False,
                   "user": request.user})


@pydici_non_public
@pydici_feature("billing_request")
def client_bill_detail(request, bill_id):
    """Display detailed bill information, metadata and bill pdf"""
    bill = ClientBill.objects.get(id=bill_id)
    return render(request, "billing/client_bill_detail.html",
                  {"bill": bill})


@pydici_non_public
@pydici_feature("billing_request")
def clientbill_delete(request, bill_id):
    """Delete client bill in early stage"""
    redirect_url = reverse("billing:client_bills_in_creation")
    try:
        bill = ClientBill.objects.get(id=bill_id)
        if bill.state in ("0_DRAFT", "0_PROPOSED"):
            bill.delete()
            messages.add_message(request, messages.INFO, _("Bill removed successfully"))
        else:
            messages.add_message(request, messages.WARNING, _("Can't remove a bill that have been sent. You may cancel it"))
            redirect_url = reverse_lazy("billing:client_bill", args=[bill.id, ])
    except Exception as e:
        messages.add_message(request, messages.WARNING, _("Can't find bill %s" % bill_id))

    return HttpResponseRedirect(redirect_url)


@pydici_non_public
@pydici_feature("billing_management")
def supplier_bill(request, bill_id=None):
    """Add or edit supplier bill"""
    if bill_id:
        try:
            bill = SupplierBill.objects.get(id=bill_id)
        except SupplierBill.DoesNotExist:
            raise Http404
    else:
        bill = None

    lead_id =request.GET.get("lead")

    if request.POST:
        form = SupplierBillForm(request.POST, request.FILES, instance=bill)
        if form.is_valid():
            bill = form.save()
            return HttpResponseRedirect(reverse_lazy("billing:supplier_bills_archive"))
    else:
        if bill:
            form = SupplierBillForm(instance=bill)
        elif lead_id:
            form = SupplierBillForm(initial={"lead": lead_id})
        else:
            form = SupplierBillForm()

    return render(request, "billing/supplier_bill_form.html",
                  {"bill_form": form,
                   "bill_id": bill.id if bill else None,
                   "can_delete": bill.state == "1_RECEIVED" if bill else False,
                   "user": request.user})


@pydici_non_public
@pydici_feature("billing_management")
def supplierbill_delete(request, bill_id):
    """Delete supplier in early stage"""
    redirect_url = reverse("billing:supplier_bills_archive")
    try:
        bill = SupplierBill.objects.get(id=bill_id)
        if bill.state == "1_RECEIVED":
            bill.delete()
            messages.add_message(request, messages.INFO, _("Bill removed successfully"))
        else:
            messages.add_message(request, messages.WARNING, _("Can't remove a bill in state %s. You may cancel it" % bill.get_state_display()))
            redirect_url = reverse_lazy("billing:supplier_bill", args=[bill.id, ])
    except Exception as e:
        messages.add_message(request, messages.WARNING, _("Can't find bill %s" % bill_id))

    return HttpResponseRedirect(redirect_url)


@pydici_non_public
@pydici_feature("billing_request")
def pre_billing(request, start_date=None, end_date=None, mine=False):
    """Pre billing page: help to identify bills to send"""
    subsidiary = get_subsidiary_from_session(request)
    if end_date is None:
        end_date = date.today().replace(day=1)
    else:
        end_date = date(int(end_date[0:4]), int(end_date[4:6]), 1)
    if start_date is None:
        start_date = previousMonth(date.today())
    else:
        start_date = date(int(start_date[0:4]), int(start_date[4:6]), 1)

    if end_date - start_date > timedelta(180):
        # Prevent excessive window that is useless would lead to deny of service
        start_date = (end_date - timedelta(180)).replace(day=1)

    if end_date < start_date:
        end_date = nextMonth(start_date)

    timeSpentBilling = {}  # Key is lead, value is total and dict of mission(total, Mission billingData)
    rates = {}  # Key is mission, value is Consultant rates dict
    internalBilling = {}  # Same structure as timeSpentBilling but for billing between internal subsidiaries

    try:
        billing_consultant = Consultant.objects.get(trigramme__iexact=request.user.username)
    except Consultant.DoesNotExist:
        billing_consultant = None
        mine = False


    fixedPriceMissions = Mission.objects.filter(nature="PROD", billing_mode="FIXED_PRICE",
                                                timesheet__working_date__gte=start_date,
                                                timesheet__working_date__lt=end_date)
    undefinedBillingModeMissions = Mission.objects.filter(nature="PROD", billing_mode=None,
                                                          timesheet__working_date__gte=start_date,
                                                          timesheet__working_date__lt=end_date)

    timespent_timesheets = Timesheet.objects.filter(working_date__gte=start_date, working_date__lt=end_date,
                                                    mission__nature="PROD", mission__billing_mode="TIME_SPENT")

    internalBillingTimesheets = Timesheet.objects.filter(working_date__gte=start_date, working_date__lt=end_date,
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

    if subsidiary: # filter on subsidiary
        fixedPriceMissions = fixedPriceMissions.filter(subsidiary=subsidiary)
        timespent_timesheets = timespent_timesheets.filter(mission__subsidiary=subsidiary)
        undefinedBillingModeMissions = undefinedBillingModeMissions.filter(subsidiary=subsidiary)

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
                   "start_date": start_date,
                   "end_date": end_date,
                   "mine": mine,
                   "user": request.user})


@pydici_non_public
@pydici_feature("billing_request")
def client_bills_in_creation(request):
    """Review client bill in preparation"""
    return render(request, "billing/client_bills_in_creation.html",
                  {"data_url": reverse('billing:client_bills_in_creation_DT'),
                   "datatable_options": ''' "order": [[4, "desc"]], "columnDefs": [{ "orderable": false, "targets": [1, 3] }]  ''',
                   "user": request.user})


@pydici_non_public
@pydici_feature("billing_request")
def client_bills_archive(request):
    """Review all client bill """
    return render(request, "billing/client_bills_archive.html",
                  {"data_url": reverse('billing:client_bills_archive_DT'),
                   "datatable_options": ''' "lengthMenu": [ 10, 25, 50, 100, 500 ], "order": [[4, "desc"]], "columnDefs": [{ "orderable": false, "targets": [1, 2, 10] }]  ''',
                   "user": request.user})


@pydici_non_public
@pydici_feature("billing_request")
def supplier_bills_archive(request):
    """Review all supplier bill """
    return render(request, "billing/supplier_bills_archive.html",
                  {"data_url": reverse('billing:supplier_bills_archive_DT'),
                   "datatable_options": ''' "order": [[4, "desc"]], "columnDefs": [{ "orderable": false, "targets": [2, 10] }]  ''',
                   "user": request.user})

@pydici_non_public
@pydici_feature("reports")
def lead_billing(request, lead_id):
    """lead / mission billing tab that display billing control and client/supplier bill list"""
    lead = Lead.objects.get(id=lead_id)
    return render(request, "billing/_lead_billing.html",
                  {"lead": lead})

@pydici_non_public
@pydici_feature("reports")
def client_billing_control_pivotable(request, filter_on_subsidiary=None, filter_on_company=None, filter_on_lead=None):
    """Check lead/mission billing."""
    subsidiary = get_subsidiary_from_session(request)
    month_to_exc_from_my_leads = [date.today().replace(day=1)]
    for i in range(6):
        month_to_exc_from_my_leads.append(nextMonth(month_to_exc_from_my_leads[-1]))
    month_to_exc_from_my_leads = [m.isoformat() for m in month_to_exc_from_my_leads]
    data = get_client_billing_control_pivotable_data(filter_on_subsidiary=filter_on_subsidiary or subsidiary,
                                                     filter_on_company=filter_on_company,
                                                     filter_on_lead=filter_on_lead,
                                                     only_active=True)
    return render(request, "billing/client_billing_control_pivotable.html",
                  {"data": data,
                   "consultant": Consultant.objects.filter(trigramme__iexact=request.user.username).first(),
                   "month_to_exc_from_my_leads": month_to_exc_from_my_leads,
                   "derivedAttributes": "{}"})


@pydici_non_public
@pydici_feature("reports")
@cache_page(60 * 60 * 24)
def graph_billing_jqp(request):
    """Nice graph bar of incomming cash from bills
    @todo: per year, with start-end date"""
    subsidiary = get_subsidiary_from_session(request)
    billsData = defaultdict(list)  # Bill graph Data
    tsData = {}  # Timesheet done work graph data
    staffingData = {}  # Staffing forecasted work graph data
    wStaffingData = {}  # Weighted Staffing forecasted work graph data
    states = ["1_SENT", "2_PAID"]
    today = date.today()
    start_date = today - timedelta(3 * 365)  # last three years
    end_date = today + timedelta(6 * 30)  # No more than 6 month forecasted
    graph_data = []  # Data that will be returned to jqplot

    # Gathering billsData
    bills = ClientBill.objects.filter(creation_date__gt=start_date, state__in=states)
    if subsidiary:
        bills = bills.filter(lead__subsidiary=subsidiary)
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
    timesheets = Timesheet.objects.filter(working_date__lt=today, working_date__gt=start_date, mission__nature="PROD")
    if subsidiary:
        timesheets = timesheets.filter(mission__subsidiary=subsidiary)
    for ts in timesheets.select_related():
        kdate = ts.working_date.replace(day=1)
        if kdate not in tsData:
            tsData[kdate] = 0  # Create key
        tsData[kdate] += ts.charge * financialConditions.get(ts.consultant_id, {}).get(ts.mission_id, 0) / 1000

    # Collect data for forecasted work according to staffing data
    staffings = Staffing.objects.filter(staffing_date__gte=today.replace(day=1), staffing_date__lt=end_date, mission__nature="PROD")
    if subsidiary:
        staffings = staffings.filter(mission__subsidiary=subsidiary)
    for staffing in staffings.select_related():
        kdate = staffing.staffing_date.replace(day=1)
        if kdate not in staffingData:
            staffingData[kdate] = 0  # Create key
            wStaffingData[kdate] = 0  # Create key
        staffingData[kdate] += staffing.charge * financialConditions.get(staffing.consultant_id, {}).get(staffing.mission_id, 0) / 1000
        wStaffingData[kdate] += staffing.charge * financialConditions.get(staffing.consultant_id, {}).get(staffing.mission_id, 0) * staffing.mission.probability / 100 / 1000

    billKdates = list(billsData.keys())
    billKdates.sort()
    isoBillKdates = [a.isoformat() for a in billKdates]  # List of date as string in ISO format

    # Draw a bar for each state
    for state in states:
        ydata = [sum([float(i.amount) / 1000 for i in x if i.state == state]) for x in sortedValues(billsData)]
        graph_data.append(list(zip(isoBillKdates, ydata)))

    # Sort keys
    tsKdates = list(tsData.keys())
    tsKdates.sort()
    isoTsKdates = [a.isoformat() for a in tsKdates]  # List of date as string in ISO format
    staffingKdates = list(staffingData.keys())
    staffingKdates.sort()
    isoStaffingKdates = [a.isoformat() for a in staffingKdates]  # List of date as string in ISO format
    wStaffingKdates = list(staffingData.keys())
    wStaffingKdates.sort()
    isoWstaffingKdates = [a.isoformat() for a in wStaffingKdates]  # List of date as string in ISO format

    # Sort values according to keys
    tsYData = sortedValues(tsData)
    staffingYData = sortedValues(staffingData)
    wStaffingYData = sortedValues(wStaffingData)

    # Draw done work
    graph_data.append(list(zip(isoTsKdates, tsYData)))

    # Draw forecasted work
    graph_data.append(list(zip(isoStaffingKdates, staffingYData)))
    graph_data.append(list(zip(isoWstaffingKdates, wStaffingYData)))

    return render(request, "billing/graph_billing_jqp.html",
                  {"graph_data": json.dumps(graph_data),
                   "series_label": [i[1] for i in ClientBill.CLIENT_BILL_STATE if i[0] in states],
                   "series_colors": COLORS,
                   "user": request.user})


@pydici_non_public
@pydici_feature("reports")
@cache_page(60 * 10)
def graph_yearly_billing(request):
    """Fiscal year billing per subsidiary"""
    bills = ClientBill.objects.filter(state__in=("1_SENT", "2_PAID"))
    years = get_fiscal_years_from_qs(bills, "creation_date")
    month = int(get_parameter("FISCAL_YEAR_MONTH"))
    data = {}
    graph_data = []
    labels = []
    growth = []
    subsidiary = get_subsidiary_from_session(request)
    if subsidiary:
        subsidiaries = [subsidiary,]
    else:
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
    for current_turnover in [sum(i) for i in zip(*list(data.values()))]:  # Total per year
        if last_turnover > 0:
            growth.append(round(100 * (current_turnover - last_turnover) / last_turnover, 1))
        else:
            growth.append(None)
        last_turnover = current_turnover

    if years[-1] == date.today().year:
        growth.pop()  # Don't compute for on-going year.

    graph_data.append(["x"] + years)  # X (years) axis

    # Add turnover per subsidiary
    for key, value in list(data.items()):
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
                   "subsidiaries_names" : json.dumps(labels),
                   "series_colors": COLORS,
                   "user": request.user})


@pydici_non_public
@pydici_feature("reports")
@cache_page(60 * 60 * 4)
def graph_outstanding_billing(request):
    """Graph outstanding billing, including overdue clients bills"""
    end = nextMonth(date.today() + timedelta(45))
    current = (end - timedelta(30) * 24).replace(day=1)
    today = date.today()
    months = []
    outstanding = []
    outstanding_overdue = []
    graph_data = []
    subsidiary = get_subsidiary_from_session(request)
    while current < end:
        months.append(current.isoformat())
        next_month = nextMonth(current)
        bills = ClientBill.objects.filter(due_date__lte=next_month, state__in=("1_SENT", "2_PAID")).exclude(payment_date__lt=current)
        if subsidiary:
            bills = bills.filter(lead__subsidiary=subsidiary)
        overdue_bills = bills.exclude(payment_date__lte=F("due_date")).exclude(payment_date__gt=next_month).exclude(due_date__gt=today)
        outstanding.append(float(bills.aggregate(Sum("amount"))["amount__sum"] or 0))
        outstanding_overdue.append(float(overdue_bills.aggregate(Sum("amount"))["amount__sum"] or 0))
        current = next_month

    graph_data.append(["x"] + months)
    graph_data.append([_("billing outstanding")] + outstanding)
    graph_data.append([_("billing outstanding overdue")] + outstanding_overdue)

    return render(request, "billing/graph_outstanding_billing.html",
                  {"graph_data": json.dumps(graph_data),
                   "series_colors": COLORS,
                   "user": request.user})