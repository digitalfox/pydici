# coding: utf-8
"""
Pydici billing views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta
import mimetypes
import json
from io import BytesIO
import os
from decimal import Decimal

from os.path import basename

from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.utils import translation
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.db.models import Sum, Q, F, Min, Max, Count
from django.db.models.functions import TruncMonth
from django.views.generic import TemplateView
from django.views.decorators.cache import cache_page
from django.forms.models import inlineformset_factory
from django.forms.utils import ValidationError
from django.contrib import messages
from django.utils.decorators import method_decorator

from django_weasyprint.views import WeasyTemplateResponse, WeasyTemplateView
from pypdf import PdfMerger, PdfReader

from billing.utils import get_billing_info, update_bill_from_timesheet, update_client_bill_from_proportion, \
    bill_pdf_filename, get_client_billing_control_pivotable_data, generate_bill_pdf, format_bill_pdf
from billing.models import ClientBill, SupplierBill, BillDetail, BillExpense, InternalBill, InternalBillDetail
from leads.models import Lead
from people.models import Consultant
from people.utils import get_team_scopes
from staffing.models import Timesheet, Mission
from staffing.views import MissionTimesheetReportPdf
from crm.models import Subsidiary
from crm.utils import get_subsidiary_from_session
from core.utils import get_fiscal_years_from_qs, get_parameter, user_has_feature
from core.utils import COLORS, nextMonth, previousMonth, get_fiscal_year
from core.decorator import pydici_non_public, PydiciNonPublicdMixin, pydici_feature, PydiciFeatureMixin
from billing.forms import BillDetailInlineFormset, BillExpenseFormSetHelper, BillExpenseInlineFormset, BillExpenseForm
from billing.forms import ClientBillForm, BillDetailForm, BillDetailFormSetHelper, SupplierBillForm, \
    InternalBillForm, InternalBillDetailForm, InternalBillDetailFormSetHelper, InternalBillDetailInlineFormset


@pydici_non_public
@pydici_feature("reports")
def bill_review(request):
    """Review of clients bills: bills overdue, due soon, or to be created"""
    today = date.today()
    wait_warning = timedelta(15)  # wait in days used to warn that a bill is due soon
    subsidiary = get_subsidiary_from_session(request)

    # Get bills overdue, due soon, litigious and recently paid
    overdue_bills = ClientBill.objects.filter(state="1_SENT", due_date__lte=today)
    overdue_bills = overdue_bills.prefetch_related("lead__responsible", "lead__subsidiary").select_related("lead__client__contact", "lead__client__organisation__company")
    soondue_bills = ClientBill.objects.filter(state="1_SENT", due_date__gt=today, due_date__lte=(today + wait_warning))
    soondue_bills = soondue_bills.prefetch_related("lead__responsible", "lead__subsidiary").select_related("lead__client__contact", "lead__client__organisation__company")
    recent_bills = ClientBill.objects.filter(state="2_PAID").order_by("-payment_date")
    recent_bills = recent_bills.prefetch_related("lead__responsible", "lead__subsidiary").select_related("lead__client__contact", "lead__client__organisation__company")
    litigious_bills = ClientBill.objects.filter(state="3_LITIGIOUS").select_related()

    # Filter bills on subsidiary if defined
    if subsidiary:
        overdue_bills = overdue_bills.filter(lead__subsidiary=subsidiary)
        soondue_bills = soondue_bills.filter(lead__subsidiary=subsidiary)
        recent_bills = recent_bills.filter(lead__subsidiary=subsidiary)
        litigious_bills = litigious_bills.filter(lead__subsidiary=subsidiary)

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
                   "billing_management": user_has_feature(request.user, "billing_management"),
                   "consultant": Consultant.objects.filter(trigramme__iexact=request.user.username).first(),
                   "user": request.user})

@pydici_non_public
@pydici_feature("billing_request")
def supplier_bills_validation(request):
    """Review and validate suppliers bills"""
    today = date.today()
    subsidiary = get_subsidiary_from_session(request)
    supplier_overdue_bills = SupplierBill.objects.filter(state__in=("1_RECEIVED", "1_VALIDATED"), due_date__lte=today)
    supplier_overdue_bills = supplier_overdue_bills.prefetch_related("lead").select_related()
    supplier_soondue_bills = SupplierBill.objects.filter(state__in=("1_RECEIVED", "1_VALIDATED"), due_date__gt=today)
    supplier_soondue_bills = supplier_soondue_bills.prefetch_related("lead").select_related()

    # Filter bills on subsidiary if defined
    if subsidiary:
        supplier_overdue_bills = supplier_overdue_bills.filter(lead__subsidiary=subsidiary)
        supplier_soondue_bills = supplier_soondue_bills.filter(lead__subsidiary=subsidiary)
    return render(request, "billing/supplier_bills_validation.html",
                  {"supplier_soondue_bills": supplier_soondue_bills,
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
             _("creation date"): bill.creation_date.replace(day=1).isoformat(),
             _("fiscal year"): get_fiscal_year(bill.creation_date)}
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
        return HttpResponseRedirect(reverse("billing:supplier_bills_validation"))
    else:
        return HttpResponseRedirect(reverse("core:forbidden"))


@pydici_non_public
@pydici_feature("billing_management")
def mark_supplierbill_paid(request, bill_id):
    """Mark the given supplier bill as paid"""
    bill = SupplierBill.objects.get(id=bill_id)
    bill.state = "2_PAID"
    bill.save()
    return HttpResponseRedirect(reverse("billing:supplier_bills_validation"))


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
        target = BytesIO()
        try:
            bill = self.context_data["bill"]
            translation.activate(bill.lang)
            bill_pdf = super(BillAnnexPDFTemplateResponse, self).rendered_content
            merger = PdfMerger()
            merger.append(PdfReader(BytesIO(bill_pdf)))
            # Add expense receipt
            for billExpense in bill.billexpense_set.all():
                if billExpense.expense and billExpense.expense.receipt_content_type() == "application/pdf":
                    merger.append(PdfReader(billExpense.expense.receipt.file))
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
            pdf = format_bill_pdf(target, bill)
            target.close()
        finally:
            translation.activate(old_lang)
            target.close()
        return pdf


class BillPdf(Bill, WeasyTemplateView):
    response_class = BillAnnexPDFTemplateResponse

    def get_filename(self):
        bill = self.get_context_data(**self.kwargs)["bill"]
        return bill_pdf_filename(bill)


class InternalBillView(PydiciNonPublicdMixin, TemplateView):
    template_name = 'billing/internal_bill.html'

    def get_context_data(self, **kwargs):
        context = super(InternalBillView, self).get_context_data(**kwargs)
        try:
            bill = InternalBill.objects.get(id=kwargs.get("bill_id"))
            context["bill"] = bill
        except InternalBill.DoesNotExist:
            bill = None
        return context

    @method_decorator(pydici_feature("billing_request"))
    def dispatch(self, *args, **kwargs):
        return super(InternalBillView, self).dispatch(*args, **kwargs)


class InternalBillAnnexPDFTemplateResponse(WeasyTemplateResponse):
    """TemplateResponse override to merge """
    @property
    def rendered_content(self):
        old_lang = translation.get_language()
        try:
            bill = self.context_data["bill"]
            translation.activate(bill.lang)
            bill_pdf = super(InternalBillAnnexPDFTemplateResponse, self).rendered_content
            pdf = format_bill_pdf(BytesIO(bill_pdf), bill)
        finally:
            translation.activate(old_lang)
        return pdf


class InternalBillPdf(InternalBillView, WeasyTemplateView):
    response_class = InternalBillAnnexPDFTemplateResponse

    def get_filename(self):
        bill = self.get_context_data(**self.kwargs)["bill"]
        return "%s-%s-%s.pdf" % (bill.bill_id, bill.buyer.code, bill.seller.code)


@pydici_non_public
@pydici_feature("billing_request")
def client_bill(request, bill_id=None):
    """Add or edit client bill"""
    billDetailFormSet = None
    billExpenseFormSet = None
    billing_management_feature = "billing_management"
    wip_status = ("0_DRAFT", "0_PROPOSED")
    forbidden = HttpResponseRedirect(reverse("core:forbidden"))
    if bill_id:
        try:
            bill = ClientBill.objects.get(id=bill_id)
            have_expenses = bill.lead.expense_set.filter(chargeable=True, billexpense__isnull=True).exists()
        except ClientBill.DoesNotExist:
            raise Http404
    else:
        bill = None
        have_expenses = False
    BillDetailFormSet = inlineformset_factory(ClientBill, BillDetail, formset=BillDetailInlineFormset, form=BillDetailForm, fields="__all__")
    BillExpenseFormSet = inlineformset_factory(ClientBill, BillExpense, formset=BillExpenseInlineFormset, form=BillExpenseForm, fields="__all__")

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
            if form.data["state"] not in wip_status and (billDetailFormSet.has_changed() or billExpenseFormSet.has_changed()):
                form.add_error("state", ValidationError(_("You can't modify bill details in that state")))
        if form.is_valid() and (billDetailFormSet is None or billDetailFormSet.is_valid()) and (billExpenseFormSet is None or billExpenseFormSet.is_valid()):
            bill = form.save()
            if billDetailFormSet:
                billDetailFormSet.save()
            if billExpenseFormSet:
                billExpenseFormSet.save()
            bill.save()  # Again, to take into account modified details.
            if bill.state in wip_status:
                success_url = reverse_lazy("billing:client_bill", args=[bill.id, ])
                # User want to add chargeable expenses ?
                if "Submit-expenses" in request.POST:
                    # compute again because user may add expenses during submit
                    expenses = bill.lead.expense_set.filter(chargeable=True, billexpense__isnull=True)
                    for expense in expenses:
                        BillExpense(bill=bill, expense=expense).save()
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
                bill = ClientBill(lead=missions[0].lead)
                bill.save()
            for mission in missions:
                if mission.billing_mode == "TIME_SPENT":
                    if request.GET.get("start_date") and request.GET.get("end_date"):
                        start_date = date(int(request.GET.get("start_date")[0:4]), int(request.GET.get("start_date")[4:6]), 1)
                        end_date = date(int(request.GET.get("end_date")[0:4]), int(request.GET.get("end_date")[4:6]), 1)
                    else:
                        start_date = previousMonth(date.today())
                        end_date = date.today().replace(day=1)
                    update_bill_from_timesheet(bill, mission, start_date, end_date)
                else:  # FIXED_PRICE mission
                    if request.GET.get("amount") and mission.price:
                        proportion = Decimal(request.GET.get("amount")) / mission.price
                    else:
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
                   "have_expenses": have_expenses,
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
    except ClientBill.DoesNotExist:
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

    lead_id = request.GET.get("lead")

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
    except SupplierBill.DoesNotExist:
        messages.add_message(request, messages.WARNING, _("Can't find bill %s" % bill_id))

    return HttpResponseRedirect(redirect_url)

@pydici_non_public
@pydici_feature("billing_management")
def internal_bill(request, bill_id=None):
    """Add or edit internal bill"""
    if bill_id:
        try:
            bill = InternalBill.objects.get(id=bill_id)
        except InternalBill.DoesNotExist:
            raise Http404
    else:
        bill = None

    internalBillDetailFormSet = None
    wip_status = ("0_DRAFT", "0_PROPOSED")

    InternalBillDetailFormSet = inlineformset_factory(InternalBill, InternalBillDetail, formset=InternalBillDetailInlineFormset,
                                                      form=InternalBillDetailForm, fields="__all__")

    if request.POST:
        form = InternalBillForm(request.POST, request.FILES, instance=bill)
        if bill and bill.state in wip_status:
            internalBillDetailFormSet = InternalBillDetailFormSet(request.POST, instance=bill)
            if form.data["state"] not in wip_status and internalBillDetailFormSet.has_changed():
                form.add_error("state", ValidationError(_("You can't modify bill details in that state")))
        if form.is_valid() and ((internalBillDetailFormSet is None) or internalBillDetailFormSet.is_valid()):
            bill = form.save()
            if internalBillDetailFormSet:
                internalBillDetailFormSet.save()
            bill.save()  # Again, to take into account modified details.
            if bill.state in wip_status:
                success_url = reverse_lazy("billing:internal_bill", args=[bill.id,],)
            else:
                success_url = request.GET.get("return_to", False) or reverse_lazy("billing:internal_bill_detail", args=[bill.id,],)
                if bill.bill_file:
                    if form.changed_data == ["state"] and internalBillDetailFormSet is None:
                        # only state has change. No need to regenerate bill file.
                        messages.add_message(request, messages.INFO, _("Bill state has been updated"))
                    elif "bill_file" in form.changed_data:
                        # a file has been provided by user himself. We must not generate a file and overwrite it.
                        messages.add_message(request, messages.WARNING, _("Using custom user file to replace current bill"))
                    elif bill.internalbilldetail_set.exists():
                        # bill file exist but authorized admin change information and do not provide custom file. Let's generate again bill file
                        messages.add_message(request, messages.WARNING, _("A new bill is generated and replace the previous one"))
                        if os.path.exists(bill.bill_file.path):
                            os.remove(bill.bill_file.path)
                        generate_bill_pdf(bill, request) # TODO: adapt it to internal bill
                else:
                    # Bill file still not exist. Let's create it
                    messages.add_message(request, messages.INFO, _("A new bill file has been generated"))
                    generate_bill_pdf(bill, request) # TODO: adapt it to internal bill
            return HttpResponseRedirect(success_url)
    else:
        if bill:
            # Create a form to edit the given bill
            form = InternalBillForm(instance=bill)
            if bill.state in wip_status:
                internalBillDetailFormSet = InternalBillDetailFormSet(instance=bill)
        else:
            # Still no bill, let's create it with its detail if at least mission or lead has been provided
            missions = []
            if request.GET.get("lead"):
                lead = Lead.objects.get(id=request.GET.get("lead"))
                missions = lead.mission_set.all()  # take all missions
            if request.GET.get("mission"):
                missions = [Mission.objects.get(id=request.GET.get("mission"))]
            if missions and request.GET.get("buyer") and request.GET.get("seller"):
                buyer = Subsidiary.objects.get(id=request.GET.get("buyer"))
                seller = Subsidiary.objects.get(id=request.GET.get("seller"))
                bill = InternalBill(buyer=buyer, seller=seller)
                bill.save()
            for mission in missions:
                # Always create internal bill as time spent by default.
                if request.GET.get("start_date") and request.GET.get("end_date"):
                    start_date = date(int(request.GET.get("start_date")[0:4]), int(request.GET.get("start_date")[4:6]), 1)
                    end_date = date(int(request.GET.get("end_date")[0:4]), int(request.GET.get("end_date")[4:6]), 1)
                else:
                    start_date = previousMonth(date.today())
                    end_date = date.today().replace(day=1)
                update_bill_from_timesheet(bill, mission, start_date, end_date)
            if bill:
                form = InternalBillForm(instance=bill)
                internalBillDetailFormSet = InternalBillDetailFormSet(instance=bill)
            else:
                # Simple virgin new form
                form = InternalBillForm()

    return render(request, "billing/internal_bill_form.html",
                  { "bill_form": form,
                    "detail_formset": internalBillDetailFormSet,
                    "detail_formset_helper": InternalBillDetailFormSetHelper(),
                    "bill_id": bill.id if bill else None,
                    "can_delete": bill.state in wip_status if bill else False,
                    "can_preview": bill.state in wip_status if bill else False,
                    "user": request.user})


@pydici_non_public
@pydici_feature("billing_management")
def internal_bill_detail(request, bill_id=None):
    """Display detailed bill information, metadata and bill pdf"""
    bill = InternalBill.objects.get(id=bill_id)
    return render(request, "billing/internal_bill_detail.html", {"bill": bill})


@pydici_non_public
@pydici_feature("billing_management")
def internalbill_delete(request, bill_id):
    """Delete supplier in early stage"""
    #TODO: implement it
    pass

@pydici_non_public
@pydici_feature("billing_request")
def pre_billing(request, start_date=None, end_date=None, mine=False):
    """Pre billing page: help to identify bills to send"""
    subsidiary = get_subsidiary_from_session(request)
    team = None
    team_consultants = None
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

    if "team_id" in request.GET:
        team = Consultant.objects.get(id=int(request.GET["team_id"]))
        team_consultants = Consultant.objects.filter(staffing_manager=team)
        mine = False

    timespent_billing = {}  # Key is lead, value is total and dict of mission(total, Mission billingData)
    internal_billing = {}  # Same structure as timeSpentBilling but for billing between internal subsidiaries

    try:
        billing_consultant = Consultant.objects.get(trigramme__iexact=request.user.username)
    except Consultant.DoesNotExist:
        billing_consultant = None
        mine = False

    fixed_price_missions = Mission.objects.filter(nature="PROD", billing_mode="FIXED_PRICE").filter(
                                                Q(timesheet__working_date__gte=start_date, timesheet__working_date__lt=end_date) |
                                                Q(end_date__gte=start_date))
    undefined_billing_mode_missions = Mission.objects.filter(nature="PROD", billing_mode=None,
                                                          timesheet__working_date__gte=start_date,
                                                          timesheet__working_date__lt=end_date)

    timespent_timesheets = Timesheet.objects.filter(working_date__gte=start_date, working_date__lt=end_date,
                                                    mission__nature="PROD", mission__billing_mode="TIME_SPENT")

    internal_billing_timesheets = Timesheet.objects.filter(working_date__gte=start_date, working_date__lt=end_date,
                                                    mission__nature="PROD")
    internal_billing_timesheets = internal_billing_timesheets.exclude(Q(consultant__company=F("mission__subsidiary")) & Q(consultant__company=F("mission__lead__subsidiary")))
    internal_billing_timesheets = internal_billing_timesheets.exclude(consultant__subcontractor=True)

    if mine:  # Filter on consultant mission/lead as responsible
        fixed_price_missions = fixed_price_missions.filter(Q(lead__responsible=billing_consultant) | Q(responsible=billing_consultant))
        undefined_billing_mode_missions = undefined_billing_mode_missions.filter(Q(lead__responsible=billing_consultant) | Q(responsible=billing_consultant))
        timespent_timesheets = timespent_timesheets.filter(Q(mission__lead__responsible=billing_consultant) | Q(mission__responsible=billing_consultant))
        internal_billing_timesheets = internal_billing_timesheets.filter(Q(mission__lead__responsible=billing_consultant) | Q(mission__responsible=billing_consultant))
    elif team:  # Filter on team
        fixed_price_missions = fixed_price_missions.filter(
            Q(lead__responsible__in=team_consultants) | Q(responsible__in=team_consultants))
        undefined_billing_mode_missions = undefined_billing_mode_missions.filter(
            Q(lead__responsible__in=team_consultants) | Q(responsible__in=team_consultants))
        timespent_timesheets = timespent_timesheets.filter(
            Q(mission__lead__responsible__in=team_consultants) | Q(mission__responsible__in=team_consultants))
        internal_billing_timesheets = internal_billing_timesheets.filter(
            Q(mission__lead__responsible__in=team_consultants) | Q(mission__responsible__in=team_consultants))

    fixed_price_missions = fixed_price_missions.order_by("lead").distinct()
    undefined_billing_mode_missions = undefined_billing_mode_missions.order_by("lead").distinct()

    if subsidiary:  # filter on subsidiary
        fixed_price_missions = fixed_price_missions.filter(subsidiary=subsidiary)
        timespent_timesheets = timespent_timesheets.filter(mission__subsidiary=subsidiary)
        undefined_billing_mode_missions = undefined_billing_mode_missions.filter(subsidiary=subsidiary)

    timesheet_data = timespent_timesheets.order_by("mission__lead", "consultant").values_list("mission", "consultant").annotate(Sum("charge"))
    timespent_billing = get_billing_info(timesheet_data)

    for internal_subsidiary in Subsidiary.objects.all():
        subsidiary_timesheet_data = internal_billing_timesheets.filter(consultant__company=internal_subsidiary)
        for target_subsidiary in Subsidiary.objects.exclude(pk=internal_subsidiary.id):
            timesheet_data = subsidiary_timesheet_data.filter(mission__lead__subsidiary=target_subsidiary)
            timesheet_data = timesheet_data .order_by("mission__lead", "consultant").values_list("mission", "consultant").annotate(Sum("charge"))
            billing_info = get_billing_info(timesheet_data)
            if billing_info:
                internal_billing[(internal_subsidiary,target_subsidiary)] = billing_info

    fixed_price_billing = []
    for mission in fixed_price_missions:
        done = mission.done_work_k()[1]
        billed = Decimal((BillDetail.objects.filter(mission=mission).aggregate(Sum("amount"))["amount__sum"] or 0) / 1000)
        fixed_price_billing.append((mission, done, billed, (mission.price or 0) - billed))

    scopes, team_current_filter, team_current_url_filter = get_team_scopes(subsidiary, team)
    if team:
        team_name = _("team %(manager_name)s") % {"manager_name": team}
    else:
        team_name = None

    return render(request, "billing/pre_billing.html",
                  {"time_spent_billing": timespent_billing,
                   "fixed_price_billing": fixed_price_billing,
                   "undefined_billing_mode_missions": undefined_billing_mode_missions,
                   "internal_billing": internal_billing,
                   "start_date": start_date,
                   "end_date": end_date,
                   "mine": mine,
                   "scope": team_name or subsidiary or _("Everybody"),
                   "team_current_filter": team_current_filter,
                   "team_current_url_filter": team_current_url_filter,
                   "scopes": scopes,
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
@pydici_feature("billing_management")
def internal_bills_in_creation(request):
    """Review internal bill in preparation"""
    return render(request, "billing/internal_bills_in_creation.html",
                  {"data_url": reverse('billing:internal_bills_in_creation_DT'),
                   "datatable_options": ''' "order": [[4, "desc"]] ''',
                   "user": request.user})

def internal_bills_archive(request):
    """Review all internal bill """
    #TODO: adjust datatable_options
    return render(request, "billing/internal_bills_archive.html",
                  {"data_url": reverse('billing:internal_bills_archive_DT'),
                   "datatable_options": ''' "lengthMenu": [ 10, 25, 50, 100, 500 ], "order": [[4, "desc"]], "columnDefs": [{ "orderable": false, "targets": [1, 2, 10] }]  ''',
                   "user": request.user})


@pydici_non_public
@pydici_feature("reports")
def lead_billing(request, lead_id):
    """lead / mission billing tab that display billing control and client/supplier bill list"""
    lead = Lead.objects.get(id=lead_id)
    return render(request, "billing/_lead_billing.html",
                  {"lead": lead,
                   "show_supplier_bills": True})


@pydici_non_public
@pydici_feature("reports")
def client_billing_control_pivotable(request):
    """Check lead/mission billing."""
    subsidiary = get_subsidiary_from_session(request)
    responsible_id = request.GET.get("responsible")
    if responsible_id:
        responsible = Consultant.objects.get(id=responsible_id)
    else:
        responsible = None
    month_to_exclude = [date.today().replace(day=1)]
    for i in range(6):
        month_to_exclude.append(nextMonth(month_to_exclude[-1]))
    month_to_exclude = [m.isoformat() for m in month_to_exclude]
    data = get_client_billing_control_pivotable_data(filter_on_subsidiary=subsidiary,
                                                     filter_on_responsible=responsible,
                                                     only_active=True)
    return render(request, "billing/client_billing_control_pivotable.html",
                  {"data": data,
                   "responsible": responsible,
                   "month_to_exclude": month_to_exclude,
                   "derivedAttributes": "{}"})


@pydici_non_public
@pydici_feature("reports")
@cache_page(60 * 60)
def graph_billing(request):
    """Bar graph of client bills by status"""
    subsidiary = get_subsidiary_from_session(request)
    bills = ClientBill.objects.filter(creation_date__gt=(date.today() - timedelta(3*365)), state__in=("1_SENT", "2_PAID"))
    if subsidiary:
        bills = bills.filter(lead__subsidiary=subsidiary)
    if bills.count() == 0:
        return HttpResponse()
    bills = bills.annotate(month=TruncMonth("creation_date")).values("month")
    bills = bills.annotate(amount_paid=Sum("amount", filter=Q(state="2_PAID")),
                           amount_sent=Sum("amount", filter=Q(state="1_SENT")))
    bills = bills.values("month", "amount_paid", "amount_sent").order_by()
    bills = [{"month": b["month"].isoformat(), "amount_paid": float(b["amount_paid"] or 0)/1000, "amount_sent": float(b["amount_sent"] or 0)/1000} for b in bills]

    return render(request, "billing/graph_billing.html",
                  {"graph_data": json.dumps(bills),
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

    if years and years[-1] == date.today().year:
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
