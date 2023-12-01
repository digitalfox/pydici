# coding: utf-8

"""
Test data factories for people module

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from datetime import date

from django.contrib.auth.models import User

from factory.django import DjangoModelFactory
import factory.fuzzy

from crm.models import Subsidiary
from people.models import Consultant, ConsultantProfile, RateObjective

CONSULTANT_PROFILES = ["consultant", "senior consultant", "manager", "director"]

class ConsultantFactory(DjangoModelFactory):
    name = factory.Faker("name")
    trigramme = factory.Sequence(lambda n: "C%s%s" % (chr(65+int(n/10)), chr(65+n%26)))
    profil = factory.fuzzy.FuzzyChoice(ConsultantProfile.objects.all())
    company = factory.fuzzy.FuzzyChoice(Subsidiary.objects.all())
    productive = factory.LazyAttribute(lambda i: i.profil != "support")

    class Meta:
        model = Consultant


class UserFactory(DjangoModelFactory):
    username = factory.Sequence(lambda n: "C%s%s" % (chr(65+int(n/10)), chr(65+n%26)))

    class Meta:
        model = User

class ProductionRateObjectiveFactory(DjangoModelFactory):
    consultant = factory.Iterator(Consultant.objects.all())
    start_date = date.today().replace(month=1, day=1)
    rate_type = "PROD_RATE"
    rate = factory.fuzzy.FuzzyInteger(50, 95)

    class Meta:
        model = RateObjective

class DailyRateObjectiveFactory(DjangoModelFactory):
    consultant = factory.Iterator(Consultant.objects.all())
    start_date = date.today().replace(month=1, day=1)
    rate_type = "DAILY_RATE"
    rate = factory.fuzzy.FuzzyInteger(800, 2500)

    class Meta:
        model = RateObjective