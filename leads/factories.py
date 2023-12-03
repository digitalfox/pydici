# coding: utf-8

"""
Test data factories for lead module

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from factory.django import DjangoModelFactory
import factory.django
import factory.fuzzy
from datetime import date, timedelta
import random

from people.models import Consultant
from crm.models import Client, Subsidiary
from staffing.factories import ProdMissionFactory
from leads.models import Lead
from billing.factories import ClientBillFactory

class LeadFactory(DjangoModelFactory):
    name = factory.Faker("bs")
    description = factory.Faker("text")
    sales = factory.fuzzy.FuzzyDecimal(10, 250, 0)
    responsible = factory.fuzzy.FuzzyChoice(Consultant.objects.all())
    start_date = factory.Faker("date_between_dates", date_start=date.today()-timedelta(3*365), date_end=date.today()+timedelta(90))
    creation_date = factory.LazyAttribute(lambda o: o.start_date - timedelta(random.randint(20, 80)))
    client = factory.fuzzy.FuzzyChoice(Client.objects.all())
    subsidiary = factory.fuzzy.FuzzyChoice(Subsidiary.objects.all())
    missions = factory.RelatedFactoryList(ProdMissionFactory, factory_related_name="lead", size=random.choice([1, 2]))

    @factory.lazy_attribute
    def state(self):
        if self.creation_date > (date.today() - timedelta(120)):
            return random.choice([s[0] for s in Lead.STATES])
        else:
            return random.choice([s[0] for s in Lead.STATES[4:]])

    @classmethod
    def _create(cls, target_class, *args, **kwargs):
        """override create to handle date with django auto_now_add"""
        creation_date = kwargs.pop("creation_date", None)
        obj = super(LeadFactory, cls)._create(target_class, *args, **kwargs)
        if creation_date is not None:
            obj.creation_date = creation_date
            obj.save()
        return obj

    class Meta:
        model = "leads.Lead"
