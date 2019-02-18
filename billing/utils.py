# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in Billing models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.apps import apps
from django.db.models import Sum

from staffing.models import Mission
from people.models import Consultant
from core.utils import to_int_or_round, nextMonth


def get_billing_info(timesheet_data):
    """compute billing information from this timesheet data
    @:param timesheet_data: value queryset with mission, consultant and charge in days
    @:return billing information as a tuple (lead, (lead total, (mission total, billing data)) """
    billing_data = {}
    for mission_id, consultant_id, charge in timesheet_data:
        mission = Mission.objects.select_related("lead").get(id=mission_id)
        if mission.lead:
            lead = mission.lead
        else:
            # Bad data, mission with nature prod without lead... This should not happened
            continue
        consultant = Consultant.objects.get(id=consultant_id)
        rates =  mission.consultant_rates()
        if not lead in billing_data:
            billing_data[lead] = [0.0, {}]  # Lead Total and dict of mission
        if not mission in billing_data[lead][1]:
            billing_data[lead][1][mission] = [0.0, []]  # Mission Total and detail per consultant
        total = charge * rates[consultant][0]
        billing_data[lead][0] += total
        billing_data[lead][1][mission][0] += total
        billing_data[lead][1][mission][1].append(
            [consultant, to_int_or_round(charge, 2), rates[consultant][0], total])

    # Sort data
    billing_data = list(billing_data.items())
    billing_data.sort(key=lambda x: x[0].deal_id)
    return billing_data


def compute_bill(bill):
    """Compute bill amount according to its details. Should only be called by clientBill model save method"""
    if bill.state in ("0_DRAFT", "0_PROPOSED"):
        amount = 0
        amount_with_vat = 0
        for bill_detail in bill.billdetail_set.all():
            if bill_detail.amount:
                amount += bill_detail.amount
            if bill_detail.amount_with_vat:
                amount_with_vat += bill_detail.amount_with_vat

        # Add expenses
        amount += bill.expensesTotal()
        amount_with_vat += bill.expensesTotalWithTaxes()

        if amount != 0:
            bill.amount = amount
        if amount_with_vat != 0:
            bill.amount_with_vat = amount_with_vat

    # Automatically compute amount with VAT if not defined
    if not bill.amount_with_vat:
        if bill.amount:
            bill.amount_with_vat = bill.amount * (1 + bill.vat / 100)


def create_client_bill_from_timesheet(mission, month):
    """Create (and return) a bill and bill detail for given mission from timesheet of given month"""
    ClientBill = apps.get_model("billing", "clientbill")
    BillDetail = apps.get_model("billing", "billdetail")
    bill = ClientBill(lead=mission.lead)
    bill.save()
    rates = mission.consultant_rates()
    timesheet_data = mission.timesheet_set.filter(working_date__gte=month, working_date__lt=nextMonth(month))
    timesheet_data = timesheet_data.order_by("consultant").values("consultant").annotate(Sum("charge"))
    for i in timesheet_data:
        consultant = Consultant.objects.get(id=i["consultant"])
        billDetail =  BillDetail(bill=bill, mission=mission, month=month, consultant=consultant, quantity=i["charge__sum"], unit_price=rates[consultant][0])
        billDetail.save()
    compute_bill(bill)  # update bill amount according to its details
    return bill


def create_client_bill_from_proportion(mission, proportion):
    """Create (and return) a bill and bill detail for given mission from proportion of mission total price"""
    ClientBill = apps.get_model("billing", "clientbill")
    BillDetail = apps.get_model("billing", "billdetail")
    bill = ClientBill(lead=mission.lead)
    bill.save()
    billDetail = BillDetail(bill=bill, mission=mission, quantity=proportion, unit_price=mission.price*1000)
    billDetail.save()
    compute_bill(bill)  # update bill amount according to its details
    return bill


def bill_pdf_filename(bill):
    """Nice name for generated pdf file"""
    try:
        filename = "%s-%s.pdf" % (bill.bill_id, bill.lead.deal_id)
    except ValueError:
        # Incomplete bill, we still want to generate the pdf
        filename = "bill.pdf"
    return filename