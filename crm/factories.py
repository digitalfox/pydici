# coding: utf-8

"""
Test data factories for crm module

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from factory.django import DjangoModelFactory
import factory.django
import factory.fuzzy
import random

from people.models import Consultant
from crm.models import BusinessSector, Client

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

class ContactFactory(DjangoModelFactory):
    name = factory.Faker("name")
    email = factory.Faker("email")
    phone = factory.Faker("phone_number")
    mobile_phone = factory.Faker("phone_number")
    fax = factory.Faker("phone_number")
    function = factory.fuzzy.FuzzyChoice(["director", "manager", "head of department", "project director"])

    @factory.post_generation
    def contact_points(obj, create, extracted, **kwargs):
        contacts = random.choices(Consultant.objects.all(), k=random.choice([1, 2, 3]))
        obj.contact_points.set(contacts)

    class Meta:
        model = "crm.Contact"

class ClientFactory(DjangoModelFactory):
    expectations = factory.fuzzy.FuzzyChoice(Client.EXPECTATIONS, getter=lambda c: c[0])
    alignment = factory.fuzzy.FuzzyChoice(Client.ALIGNMENT, getter=lambda c: c[0])
    contact = factory.SubFactory(ContactFactory)
    class Meta:
        model = "crm.Client"

class ClientOrganisationFactory(DjangoModelFactory):
    name = factory.Iterator(["IT", "digital", "marketing", "supply chain", "board", "finance", "HR"])
    client = factory.RelatedFactory(ClientFactory, factory_related_name="organisation")
    class Meta:
        model = "crm.ClientOrganisation"

class CompanyFactory(AbstractCompanyFactory):
    businessOwner = factory.fuzzy.FuzzyChoice(Consultant.objects.filter(profil__level__gt=0))
    business_sector = factory.fuzzy.FuzzyChoice(BusinessSector.objects.all())
    clientorganisation = factory.RelatedFactoryList(ClientOrganisationFactory,  factory_related_name="company", size=2)

    class Meta:
        model = "crm.Company"

