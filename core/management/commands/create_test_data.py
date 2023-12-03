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
from django.db.transaction import atomic
from django.contrib.auth.models import User, Group

from crm.factories import SubsidiaryFactory, CompanyFactory, SupplierFactory
from crm.models import BusinessSector, Subsidiary
from people.factories import CONSULTANT_PROFILES, ConsultantFactory, UserFactory, DailyRateObjectiveFactory, ProductionRateObjectiveFactory
from people.models import ConsultantProfile, Consultant
from core.models import GroupFeature, FEATURES, Parameter
from leads.factories import LeadFactory
from leads.models import Lead
from staffing.models import Mission, FinancialCondition, Staffing, Timesheet
from staffing.factories import MarketingProductFactory, OtherStaffingFactory
from billing.factories import ClientBillFactory
from core.utils import nextMonth

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

        # Staffing, financial conditions and timesheet
        OtherStaffingFactory.create_batch((N_CONSULTANTS * 4 * 2))
        create_prod_staffing_and_financial_conditions()
        create_timesheet()

        # Bills
        ClientBillFactory.create_batch(N_LEADS * 2)



@atomic
def create_static_data():
    # Business sector
    for bs in ["Information Technology", "Health Care", "Financials", "Consumer Goods",
               "Communication Services", "Industrials", "Energy", "Utilities", "Real Estate", "Materials"]:
        BusinessSector(name=bs).save()

    # Consultant profiles
    for level, profile in enumerate(CONSULTANT_PROFILES):
        ConsultantProfile(name=profile, level=level).save()
    ConsultantProfile(name="support", level=3).save()

    # Paratemers
    Parameter(key="FISCAL_YEAR_MONTH", value="1", type="FLOAT").save()


@atomic
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

@atomic
def other_missions():
    subsidiary = Subsidiary.objects.first()
    for name in ["holidays", "non-staff"]:
        Mission(description=name, probability=100, nature="HOLIDAYS", subsidiary=subsidiary).save()
    for name in ["management", "pre-sale", "training", "R&D", "marketing", "admin"]:
        Mission(description=name, probability=100, nature="NONPROD", subsidiary=subsidiary).save()

@atomic
def create_prod_staffing_and_financial_conditions():
    for subsidiary in Subsidiary.objects.all():
        consultants = Consultant.objects.filter(company=subsidiary)
        for mission in Mission.objects.filter(nature="PROD", lead__subsidiary=subsidiary, lead__state__in=("OFFER_SENT", "NEGOCIATION", "WON")):
            for consultant in consultants.order_by("?")[:random.randint(2, 5)]:
                FinancialCondition(consultant=consultant, mission=mission,daily_rate=random.randint(800, 2500)).save()
                if mission.lead.state == "WON":
                    m = mission.lead.creation_date.replace(day=1)
                else:
                    m = date.today().replace(day=1)
                for i in range(4):
                    Staffing(consultant=consultant, mission=mission, staffing_date=m, charge=random.randint(4, 8)).save()
                    m = nextMonth(m)

@atomic
def create_timesheet():
    start = (date.today() - timedelta(365)).replace(day=1)
    end = date.today()
    day = timedelta(1)
    for consultant in Consultant.objects.all():
        current_day = start
        missions = Mission.objects.filter(staffing__consultant=consultant)
        while current_day < end:
            current_day += day
            if current_day.weekday() >= 5:
                continue
            Timesheet(consultant=consultant, mission=random.choice(missions), charge=1, working_date=current_day).save()