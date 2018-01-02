# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in Billing models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.template.loader import get_template
from django.template import Context
from django.core.files.base import ContentFile

import weasyprint

from staffing.models import Mission
from people.models import Consultant
from core.utils import to_int_or_round


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
    billing_data = billing_data.items()
    billing_data.sort(key=lambda x: x[0].deal_id)
    return billing_data


def compute_bill(bill):
    """Compute bill amount according to its details and save it"""
    if bill.state == "0_DRAFT":
        amount = 0
        amount_with_vat = 0
        for bill_detail in bill.billdetail_set.all():
            if bill_detail.amount:
                amount += bill_detail.amount
            if bill_detail.amount_with_vat:
                amount_with_vat += bill_detail.amount_with_vat
        if amount != 0:
            bill.amount = amount
        if amount_with_vat != 0:
            bill.amount_with_vat = amount_with_vat
    # Automatically compute amount with VAT if not defined
    if not bill.amount_with_vat:
        if bill.amount:
            bill.amount_with_vat = bill.amount * (1 + bill.vat / 100)

def generate_bill_pdf(bill, url):
    """Create pdf and attached it to bill object"""
    template = get_template("billing/bill.html")
    context = Context({"bill": bill})
    html = template.render(context)
    pdf = weasyprint.HTML(string=html, base_url=url).write_pdf()
    content = ContentFile(pdf)
    bill.bill_file.save(u"generated pdf", content)
    bill.save()