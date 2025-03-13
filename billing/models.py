# coding: utf-8
"""
Database access layer for pydici billing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from datetime import date, datetime, timedelta
from time import strftime

from os.path import join
import os.path
from decimal import Decimal
from base64 import b64encode
from io import BytesIO

from django.db import models
from django.db.models import Sum, Min, Max, Count
from django.utils.translation import gettext_lazy as _
from django.core.files.storage import FileSystemStorage
from django.urls import reverse
from django.conf import settings

from auditlog.models import AuditlogHistoryField

from leads.models import Lead
from staffing.models import Mission, Timesheet
from people.models import Consultant
from expense.models import Expense
from crm.models import Supplier
from billing.utils import compute_bill, get_bill_id_from_path
from core.utils import sanitizeName, nextMonth
from core.models import CLIENT_BILL_LANG
from people.tasks import compute_consultant_tasks


# Custom storage that hook static url to custom view
# Really used to have proper link in admin page

class BillStorage(FileSystemStorage):
    def __init__(self, nature="client"):
        super(BillStorage, self).__init__(location=join(settings.PYDICI_ROOTDIR, "data", "bill", nature))
        self.nature = nature

    def url(self, name):
        try:
            bill_id = get_bill_id_from_path(name)
            if self.nature == "client":
                return reverse("billing:bill_file", kwargs={"bill_id": bill_id, "nature": "client"})
            else:
                return reverse("billing:bill_file", kwargs={"bill_id": bill_id, "nature": "supplier"})
        except Exception:
            # Don't display URL if Bill does not exist or path is invalid
            return ""


# This utils function is here and not in utils module
# to avoid circular import loop, as utils module import models
def bill_file_path(instance, filename):
    """Format relative path to Storage of bill"""
    return join(strftime("%Y"), strftime("%m"),
                str(instance.id), sanitizeName(filename))


def default_due_date():
    return date.today() + timedelta(30)


def default_bill_id():
    return datetime.now().isoformat()


class AbstractBill(models.Model):
    """Abstract class that factorize ClientBill and SupplierBill fields and logic"""
    lead = models.ForeignKey(Lead, verbose_name=_("Lead"), on_delete=models.CASCADE)
    bill_id = models.CharField(_("Bill id"), max_length=200, unique=True, default=default_bill_id)
    creation_date = models.DateField(_("Creation date"), default=date.today)
    due_date = models.DateField(_("Due date"), default=default_due_date)
    payment_date = models.DateField(_("Payment date"), blank=True, null=True)
    comment = models.CharField(_("Comments"), max_length=500, blank=True, null=True)
    amount = models.DecimalField(_("Amount (€ excl tax)"), max_digits=10, decimal_places=2, blank=True, null=True)
    amount_with_vat = models.DecimalField(_("Amount (€ incl tax)"), max_digits=10, decimal_places=2, blank=True,
                                          null=True)
    vat = models.DecimalField(_("VAT (%)"), max_digits=4, decimal_places=2,
                              default=float(settings.PYDICI_DEFAULT_VAT_RATE))
    expenses = models.ManyToManyField(Expense, blank=True, limit_choices_to={"chargeable": True}, verbose_name=_("expenses"))
    expenses_with_vat = models.BooleanField(_("Charge expense with VAT"), default=True)

    def __str__(self):
        if self.bill_id:
            return "%s (%s)" % (self.bill_id, self.id)
        else:
            return str(self.id)

    def payment_wait(self):
        """Time between payment and due date"""
        if self.payment_date:
            wait = self.payment_date - self.due_date
        else:
            wait = date.today() - self.due_date
        return wait.days

    def payment_delay(self):
        """Time between creation and payment"""
        if self.payment_date:
            wait = self.payment_date - self.creation_date
        else:
            wait = date.today() - self.creation_date
        return wait.days

    def creation_lag(self):
        """Time between bill creation and earliest possible date. Worst case is considered when bill has multiple detail lines"""
        lag = []
        if self.billdetail_set.count() == 0:
            # Either bill has no detail (in creation, only expenses...) or is in old format with no details
            return None
        for detail in self.billdetail_set.all():
            if detail.mission.billing_mode == "FIXED_PRICE":
                bills = list(self.lead.clientbill_set.all().order_by("creation_date"))
                idx = bills.index(self)  # rank of bill in lead bills
                mission_boundaries = detail.mission.timesheet_set.aggregate(Min("working_date"), Max("working_date"))
                if idx == 0:  # first bill
                    if mission_boundaries["working_date__min"]:
                        lag.append(self.creation_date - mission_boundaries["working_date__min"])
                elif idx == len(bills) - 1:  # last bill
                    if mission_boundaries["working_date__max"]:
                        lag.append(self.creation_date - mission_boundaries["working_date__max"])
            elif detail.mission.billing_mode == "TIME_SPENT":
                lag.append(self.creation_date - nextMonth(detail.month))
        if lag:
            return max(lag).days

    def bill_file_url(self):
        """Return url if file exists, else #"""
        try:
            return self.bill_file.url
        except ValueError:
            return "#"

    def vat_amount(self):
        return self.amount_with_vat - self.amount

    def save(self, *args, **kwargs):
        super(AbstractBill, self).save(*args, **kwargs)  # Save it
        if "force_insert" in kwargs: kwargs.pop("force_insert")
        if self.lead.responsible:
            compute_consultant_tasks.delay(self.lead.responsible.id)

        if self.bill_file:
            bill_id = get_bill_id_from_path(self.bill_file.name)
            if bill_id == "None":
                # Bill file was saved prior ID generation. Let's move it to proper directory name
                old_file_path = self.bill_file.path
                self.bill_file.name = bill_file_path(self, os.path.basename(self.bill_file.name))  # Define new name
                os.makedirs(os.path.dirname(self.bill_file.path), exist_ok=True) # Create dir if needed (it should)
                os.rename(old_file_path, self.bill_file.path)  # Move file
                super(AbstractBill, self).save(*args, **kwargs)  # Save it again with new path

    class Meta:
        abstract = True
        ordering = ["lead__client__organisation__company", "creation_date"]


class ClientBill(AbstractBill):
    CLIENT_BILL_STATE = (
        ('0_DRAFT', _("Draft")),
        ('0_PROPOSED', _("Proposed")),
        ('1_SENT', _("Sent")),
        ('2_PAID', _("Paid")),
        ('3_LITIGIOUS', _("Litigious")),
        ('4_CANCELED', _("Canceled")),)

    state = models.CharField(_("State"), max_length=30, choices=CLIENT_BILL_STATE, default="0_DRAFT")
    bill_file = models.FileField(_("Bill File"), max_length=500, upload_to=bill_file_path,
                                 storage=BillStorage(nature="client"), null=True, blank=True)
    anonymize_profile = models.BooleanField(_("Anonymize profile name"), default=False)
    include_timesheet = models.BooleanField(_("Include timesheet"), default=False)
    lang = models.CharField(_("Language"), max_length=10, choices=CLIENT_BILL_LANG, null=True, blank=True)
    client_comment = models.CharField(_("Client comments"), max_length=500, blank=True, null=True)
    client_deal_id = models.CharField(_("Client deal id"), max_length=100, blank=True)
    allow_duplicate_expense = models.BooleanField(_("Allow to bill twice an expense"), default=False)  # Useful after credit note
    add_facturx_data = models.BooleanField(_("Add Factur-X embedded information"), default=False)

    history = AuditlogHistoryField()

    def client(self):
        if self.lead.paying_authority:
            return "%s via %s" % (self.lead, self.lead.paying_authority.short_name())
        else:
            return str(self.lead)

    def taxes(self):
        """Return taxes subtotal grouped by taxe rate like this [[20, 1923.23], [10, 152]]"""
        taxes = {}
        for detail in self.billdetail_set.all():
            taxes[detail.vat] = taxes.get(detail.vat, 0) + (detail.amount_with_vat - detail.amount)
        for billexpense in self.billexpense_set.all():
            if not self.vat in taxes:
                taxes[self.vat] = 0
            taxes[self.vat] += billexpense.amount_with_vat - billexpense.amount
        return list(taxes.items())

    def expensesTotalWithTaxes(self):
        """Returns the total sum (with added taxes) of all expenses of this bill"""
        return sum([b.amount_with_vat for b in self.billexpense_set.all()])

    def expensesTotal(self):
        """Returns the total sum (without added taxes) of all expenses of this bill"""
        return list(self.billexpense_set.aggregate(Sum("amount")).values())[0] or 0

    def prestationsTotal(self):
        """Returns total of this bill without taxes and expenses"""
        return list(self.billdetail_set.aggregate(Sum("amount")).values())[0] or 0

    def bill_data(self):
        """Return bill data in formatted way to be included inline in a html page"""
        response = ""
        if self.bill_file:
            data = BytesIO()
            for chunk in self.bill_file.chunks():
                data.write(chunk)

            data = b64encode(data.getvalue()).decode()
            response = "<object data='data:application/pdf;base64,%s' type='application/pdf' width='100%%' height='100%%'></object>" % data

        return response

    def get_absolute_url(self):
        return reverse("billing:client_bill_detail", args=[self.id,])

    def save(self, *args, **kwargs):
        super(ClientBill, self).save(*args, **kwargs)  # Save it to create pk
        if "force_insert" in kwargs: kwargs.pop("force_insert")
        if not self.lang:
            self.lang = self.lead.client.organisation.billing_lang
        if self.client_deal_id == "":  # First, try with mission client_deal_id if defined and if only one mission
            if self.billdetail_set.aggregate(Count("mission", distinct=True))["mission__count"] == 1:
                self.client_deal_id = self.billdetail_set.first().mission.client_deal_id
        if self.client_deal_id == "" and self.lead.client_deal_id: # Default to lead client deal id if still blank
            self.client_deal_id = self.lead.client_deal_id
        if self.state in ("0_DRAFT", "0_PROPOSED"):
            compute_bill(self)
            # Update creation and due date till bill is not really sent
            self.due_date = date.today() + (self.due_date - self.creation_date) # shift with same timeframe
            self.creation_date = date.today()
        # Automatically set payment date for paid bills
        if self.state == "2_PAID" and not self.payment_date:
            self.payment_date = date.today()
        # Automatically switch as paid bills with payment date
        elif self.state == "1_SENT" and self.payment_date:
            self.state = "2_PAID"
        super(ClientBill, self).save(*args, **kwargs)  # Save it

    class Meta:
        verbose_name = _("Client Bill")
        indexes = [models.Index(fields=["state", "due_date"]),]


class SupplierBill(AbstractBill):
    SUPPLIER_BILL_STATE = (
        ('1_RECEIVED', _("Received")),
        ('1_VALIDATED', _("Validated")),
        ('2_PAID', _("Paid")),
        ('3_LITIGIOUS', _("Litigious")),
        ('4_CANCELED', _("Canceled")),)
    state = models.CharField(_("State"), max_length=30, choices=SUPPLIER_BILL_STATE, default="1_RECEIVED")
    bill_file = models.FileField(_("File"), max_length=500, upload_to=bill_file_path,
                                 storage=BillStorage(nature="supplier"))
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    supplier_bill_id = models.CharField(_("Supplier Bill id"), max_length=200)

    def expected_billing(self):
        """Expected billing amount for supplier / lead of this bill"""
        total_expected = 0
        already_paid = SupplierBill.objects.filter(supplier=self.supplier, lead=self.lead,
                                                   state__in=("1_VALIDATED", "2_PAID"))
        already_paid = already_paid.aggregate(Sum("amount"))["amount__sum"] or 0

        # Add spent time on missions of this lead
        for mission in self.lead.mission_set.all():
            rates = dict([(i.id, j[1] or 0) for i, j in mission.consultant_rates().items()])  # switch to consultant id
            timesheets = Timesheet.objects.filter(mission=mission, working_date__lt=date.today().replace(day=1))
            for consultant in mission.consultants().filter(subcontractor=True, subcontractor_company=self.supplier):
                days = timesheets.filter(consultant=consultant).aggregate(Sum("charge"))["charge__sum"] or 0
                total_expected += days * rates.get(consultant.id, 0)

        # Add supplier expenses
        supplier_consultants = [c.trigramme.lower() for c in self.supplier.consultant_set.all()]
        expenses = Expense.objects.filter(lead=self.lead, state__in=("VALIDATED", "CONTROLLED"), user__username__in=supplier_consultants)
        total_expected += float(expenses.aggregate(Sum("amount"))["amount__sum"] or 0)

        return total_expected - float(already_paid)


    def save(self, *args, **kwargs):
        # Save it first to define pk and allow browsing relationship
        super(SupplierBill, self).save(*args, **kwargs)
        # Automatically set payment date for paid bills
        if self.state == "2_PAID" and not self.payment_date:
            self.payment_date = date.today()
        # Automatically switch as paid bills with payment date
        elif self.state == "1_RECEIVED" and self.payment_date:
            self.state = "2_PAID"
        super(SupplierBill, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("billing:supplier_bill", args=[self.id,])

    class Meta:
        verbose_name = _("Supplier Bill")
        unique_together = (("supplier", "supplier_bill_id"),)


class BillDetail(models.Model):
    """Lines of a client bill that describe what's actually billed for mission"""
    bill = models.ForeignKey(ClientBill, on_delete=models.CASCADE)
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE)
    month = models.DateField(null=True)
    consultant = models.ForeignKey(Consultant, null=True, blank=True, on_delete=models.CASCADE)
    quantity = models.FloatField(_("Quantity"))
    unit_price = models.DecimalField(_("Unit price (€)"), max_digits=10, decimal_places=2)
    amount = models.DecimalField(_("Amount (€ excl tax)"), max_digits=10, decimal_places=2, blank=True, null=True)
    amount_with_vat = models.DecimalField(_("Amount (€ incl tax)"), max_digits=10, decimal_places=2, blank=True,
                                          null=True)
    vat = models.DecimalField(_("VAT (%)"), max_digits=4, decimal_places=2,
                              default=Decimal(settings.PYDICI_DEFAULT_VAT_RATE))
    label = models.CharField(_("Label"), max_length=200, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.unit_price and self.quantity:
            self.amount = Decimal(self.unit_price) * Decimal(self.quantity)
        else:
            self.amount = 0

        # compute amount with VAT if amount is defined
        if self.amount:
            self.amount_with_vat = self.amount * (1 + self.vat / 100)
        # compute amount if not defined and amount with VAT is defined
        elif self.amount_with_vat:
            self.amount = self.amount_with_vat / (1 + self.vat / 100)
        else:
            self.amount_with_vat = 0
        super(BillDetail, self).save(*args, **kwargs)  # Save it

    class Meta:
        ordering = ("mission", "month", "consultant")


class BillExpense(models.Model):
    """Lines of a client bill that describe what's actually billed for expenses and generic stuff"""
    bill = models.ForeignKey(ClientBill, on_delete=models.CASCADE)
    expense = models.ForeignKey(Expense, verbose_name=_("Expense"), null=True, blank=True, on_delete=models.SET_NULL)
    expense_date = models.DateField(_("Expense date"), null=True)
    amount = models.DecimalField(_("Amount (€ excl tax)"), max_digits=10, decimal_places=2, null=True, blank=True)
    amount_with_vat = models.DecimalField(_("Amount (€ incl tax)"), max_digits=10, decimal_places=2, null=True, blank=True)
    label = models.CharField(_("Description"), max_length=200, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.expense:  # use expense data to fill in data if not provided
            if not self.expense_date:  # Use expense date if not provided
                self.expense_date = self.expense.expense_date
            if not self.amount:  # Use expense amount if not provided
                self.amount = self.expense.amount
            if not self.label: # Use expense description
                self.label = self.expense.description

        # compute amount with VAT if amount is defined
        if self.amount:
            self.amount_with_vat = self.amount * (1 + self.bill.vat / 100)
        # compute amount if not defined and amount with VAT is defined
        elif self.amount_with_vat:
            self.amount = self.amount_with_vat / (1 + self.bill.vat / 100)

        super(BillExpense, self).save(*args, **kwargs)

    class Meta:
        ordering = ("expense_date",)