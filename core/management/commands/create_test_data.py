# coding: utf-8

"""
Create test / demo data

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
import random
from datetime import date, datetime, timedelta

from django.core.management import BaseCommand
from django.db.models import F
from django.contrib.auth.models import User, Group

from crm.factories import SubsidiaryFactory, CompanyFactory, SupplierFactory
from crm.models import BusinessSector, Subsidiary
from people.factories import CONSULTANT_PROFILES, ConsultantFactory, UserFactory, DailyRateObjectiveFactory, ProductionRateObjectiveFactory
from people.models import ConsultantProfile, Consultant
from core.models import GroupFeature, FEATURES
from leads.factories import LeadFactory
from leads.models import Lead
from staffing.models import Mission
from staffing.factories import MarketingProductFactory, ProdStaffingFactory, OtherStaffingFactory

N_SUBSIDIARIES = 3
N_CONSULTANTS = 50
N_COMPANIES = 30
N_SUPPLIERS = 5
N_LEADS = 200
N_MARKET_PRODUCTS = 8

class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        create_static_data()

        # Subsidiary
        SubsidiaryFactory.create_batch(N_SUBSIDIARIES)

        # Peoples
        ConsultantFactory.create_batch(N_CONSULTANTS)
        UserFactory.create_batch(N_CONSULTANTS)
        DailyRateObjectiveFactory.create_batch(N_CONSULTANTS)
        ProductionRateObjectiveFactory.create_batch(N_CONSULTANTS)
        set_managers()
        set_user_permissions()

        # Client and suppliers
        CompanyFactory.create_batch(N_COMPANIES)
        SupplierFactory.create_batch(N_SUPPLIERS)

        # Leads and missions
        MarketingProductFactory.create_batch(N_MARKET_PRODUCTS)
        LeadFactory.create_batch(N_LEADS)
        lastweek = datetime.now() - timedelta(days=7)
        Lead.objects.all().update(update_date=lastweek)

        # Non prod and holidays missions
        other_missions()

        # Staffing
        ProdStaffingFactory.create_batch(N_CONSULTANTS * 4 * 3)
        OtherStaffingFactory.create_batch((N_CONSULTANTS * 4 * 2))


def create_static_data():
    # Business sector
    for bs in ["Information Technology", "Health Care", "Financials", "Consumer Goods",
               "Communication Services", "Industrials", "Energy", "Utilities", "Real Estate", "Materials"]:
        BusinessSector(name=bs).save()

    # Consultant profiles
    for level, profile in enumerate(CONSULTANT_PROFILES):
        ConsultantProfile(name=profile, level=level).save()
    ConsultantProfile(name="support", level=3).save()

def set_managers():
    Consultant.objects.filter(profil__name="director").update(manager=F("id"), staffing_manager=F("id"))
    for subsidiary in Subsidiary.objects.all():
        managers = Consultant.objects.filter(company=subsidiary, profil__name__in=("manager", "director"))
        for consultant in Consultant.objects.filter(company=subsidiary):
            manager = random.choice(managers)
            consultant.manager = manager
            consultant.staffing_manager = manager
            consultant.save()

def set_user_permissions():
    consultants_group = Group(name="consultants")
    consultants_group.save()
    for feature in FEATURES:
        GroupFeature(group=consultants_group, feature=feature).save()
    consultants_group.user_set.add(*User.objects.all())
    u = User.objects.first()
    u.is_superuser = True
    u.is_staff = True
    u.save()

def other_missions():
    subsidiary = Subsidiary.objects.first()
    for name in ["holidays", "non-staff"]:
        Mission(description=name, probability=100, nature="HOLIDAYS", subsidiary=subsidiary).save()
    for name in ["management", "pre-sale", "training", "R&D", "marketing", "admin"]:
        Mission(description=name, probability=100, nature="NONPROD", subsidiary=subsidiary).save()