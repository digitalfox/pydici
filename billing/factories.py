# coding: utf-8

"""
Test data factories for billing module

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from decimal import Decimal
from factory.django import DjangoModelFactory
import factory.django
import factory.fuzzy
import random
from datetime import date, timedelta

from django.db.models import Min, Max

from people.models import Consultant
from leads.models import Lead



class BillDetailFactory(DjangoModelFactory):
    mission = factory.LazyAttribute(lambda o: o.bill.lead.mission_set.order_by("?")[0])
    consultant = Consultant.objects.first()
    consultant_post = factory.PostGeneration(lambda o, c, e: setattr(o, "consultant", random.choice(o.mission.consultants() or [Consultant.objects.first()])))
    quantity = factory.fuzzy.FuzzyInteger(4, 8)
    unit_price = factory.fuzzy.FuzzyInteger(800, 2500)

    @factory.post_generation
    def month_post(self, created, extracted):
        start, end = self.mission.timesheet_set.aggregate(Min("working_date"), Max("working_date")).values()
        self.month = random.choice([start, end]).replace(day=1)

    class Meta:
        model = "billing.BillDetail"

class ClientBillFactory(DjangoModelFactory):
    lead = factory.fuzzy.FuzzyChoice(Lead.objects.filter(state="WON"))
    state = factory.fuzzy.FuzzyChoice(["0_DRAFT", "0_PROPOSED"] + ["1_SENT"] + ["2_PAID"]*10)
    bill_id = factory.Sequence(lambda i: "FAC%02d" % i)
    creation_date = factory.LazyAttribute(lambda o: o.lead.start_date + timedelta(random.randint(0, 100)))
    amount = factory.LazyAttribute(lambda o: random.randint(1000*int(o.lead.sales/4), 1000*int(o.lead.sales/2)))
    bill_details = factory.RelatedFactoryList(BillDetailFactory, factory_related_name="bill", size=random.randint(1, 4))

    class Meta:
        model = "billing.ClientBill"
