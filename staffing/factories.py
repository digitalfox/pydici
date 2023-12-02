# coding: utf-8

"""
Test data factories for staffing module

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from datetime import date

from factory.django import DjangoModelFactory
import factory.fuzzy

from crm.models import Subsidiary
from staffing.models import Mission, MarketingProduct
from leads.models import Lead

class MarketingProductFactory(DjangoModelFactory):
    code = factory.Sequence(lambda n: "MP%02d" % n)
    description = factory.Iterator(["Audit", "Development", "UX", "CyberSec", "Project Management", "Datascience", "Strategy", "Devops" ])
    subsidiary = factory.fuzzy.FuzzyChoice(Subsidiary.objects.all())

    class Meta:
        model = "staffing.MarketingProduct"

class ProdMissionFactory(DjangoModelFactory):
    nature = "PROD"
    billing_mode = factory.fuzzy.FuzzyChoice([m[0] for m in Mission.BILLING_MODES])
    marketing_product = factory.fuzzy.FuzzyChoice(MarketingProduct.objects.all())
    responsible = factory.SelfAttribute("lead.responsible")
    subsidiary = factory.SelfAttribute("lead.subsidiary")
    price = factory.SelfAttribute("lead.sales")
    description = factory.Faker("word")
    active = factory.LazyAttribute(lambda o: o.lead.state in [s[0] for s in Lead.STATES[4:]])

    @factory.lazy_attribute
    def probability(self):
        if self.lead.state == "WON":
            return 100
        elif self.lead.state in ("LOST", "FORGIVEN", "SLEEP"):
            return 0
        else:
            return 50

    class Meta:
        model = "staffing.Mission"