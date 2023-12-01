# coding: utf-8

"""
Test data factories for crm module

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from factory.django import DjangoModelFactory
import factory.django
import factory.fuzzy

from people.models import Consultant
from crm.models import BusinessSector

class AbstractAddressFactory(DjangoModelFactory):
    street = factory.Faker("street_address")
    city = factory.Faker("city")
    zipcode = factory.Faker("postcode")
    country = factory.Faker("country_code")
    billing_street = factory.LazyAttribute(lambda o: o.street)
    billing_city = factory.LazyAttribute(lambda o: o.city)
    billing_zipcode = factory.LazyAttribute(lambda o: o.zipcode)
    billing_country = factory.LazyAttribute(lambda o: o.country)

class AbstractLegalInformationFactory(DjangoModelFactory):
    legal_description = factory.Faker("text")
    legal_id = factory.Faker("isbn10")
    vat_id = factory.Faker("isbn10")

class AbstractCompanyFactory(AbstractAddressFactory, AbstractLegalInformationFactory):
    name = factory.Faker("company")
    web = factory.Faker("url")
    code = factory.Sequence(lambda n: "C%d" % n)

class SubsidiaryFactory(AbstractCompanyFactory):
    commercial_name = factory.LazyAttribute(lambda o: o.name)
    code = factory.Sequence(lambda n: "S%d" % n)
    payment_description = "payment by bank transfer"

    class Meta:
        model = "crm.Subsidiary"

class CompanyFactory(AbstractCompanyFactory):
    businessOwner = factory.fuzzy.FuzzyChoice(Consultant.objects.filter(profil__level__gt=0))
    business_sector = factory.fuzzy.FuzzyChoice(BusinessSector.objects.all())

    class Meta:
        model = "crm.Company"