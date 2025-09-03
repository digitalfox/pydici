# coding: utf-8
"""
Test cases for staffing
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@author: Aurélien Gateau (mail@agateau.com)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from unittest import mock
from io import StringIO
import csv
from datetime import date, timedelta

from django.test import TestCase, override_settings
from unittest import skipIf
from django.core.cache import cache
from django.urls import reverse
from django.contrib.auth.models import User
from django.forms import inlineformset_factory

from staffing import utils
from leads.models import Lead
from staffing.forms import MissionStaffingInlineFormset, StaffingForm
from staffing.models import Mission, Staffing, Timesheet, FinancialCondition, Holiday
from staffing.optim import solve_pdc, display_solver_solution
from people.models import Consultant, RateObjective
from core.utils import previousMonth, nextMonth
from core.tests import PYDICI_FIXTURES, TEST_USERNAME, setup_test_user_features


class TimeStringConversionTest(TestCase):
    def test_prepare_value(self):
        data = (
            # This value is how the percent representing 0:15 is stored in the
            # DB on the staging server
            (0.0357142857142857, '0:15'),
        )
        for percent, expected in data:
            output = utils.time_string_for_day_percent(percent, day_duration=7)
            self.assertEquals(output, expected)

    def test_convert_round_trip(self):
        data = ('0:15', '1:01', '2:30', '0:01', '8:00')
        day_duration = 7
        for input_str in data:
            percent = utils.day_percent_for_time_string(input_str, day_duration)
            output_str = utils.time_string_for_day_percent(percent, day_duration)
            self.assertEquals(output_str, input_str)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class StaffingModelTest(TestCase):
    fixtures = PYDICI_FIXTURES

    def test_save_mission_and_active_client(self):
        mission = Mission.objects.get(id=1)
        mission.save()
        lead = mission.lead
        for lead in Lead.objects.filter(id__in=(1, 2, 3)):
            # Set lead as won to allow client passivation when mission are archived
            lead.state = "WON"
            lead.save()
        mission.active = False
        self.assertTrue(mission.lead.client.active)  # Client is active by default and mission is not saved
        mission.save()
        self.assertFalse(mission.lead.client.active)  # Client should be flag as inactive too
        # Now with a client that has two mission in two different leads
        mission = Mission.objects.get(id=2)
        mission.save()
        self.assertTrue(mission.lead.client.active)
        mission.active = False
        mission.save()
        self.assertTrue(mission.lead.client.active)  # Client is still active because another mission is active
        otherMission = Mission.objects.get(id=3)
        otherMission.active = False
        otherMission.save()
        mission = Mission.objects.get(id=2)  # Read mission from database to avoid nasty cache effect
        self.assertFalse(mission.lead.client.active)  # All missions are now archived. Client is no more active

    def test_save_mission_and_forecast(self):
        mission = Mission.objects.get(id=1)
        mission.save()
        self.assertNotEqual(mission.staffing_set.count(), 0)
        mission.active = False
        mission.save()
        self.assertEqual(mission.staffing_set.count(), 0)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class StaffingViewsTest(TestCase):
    fixtures = PYDICI_FIXTURES

    def setUp(self):
        setup_test_user_features()
        self.test_user = User.objects.get(username=TEST_USERNAME)

    @skipIf(date.today().day == 1, "not supported the first day of month :-)")
    def test_mission_timesheet(self):
        # TODO: this test fails when executed on the first day on the month
        self.client.force_login(self.test_user)
        current_month = date.today().replace(day=1)
        next_month = nextMonth(current_month)
        previous_month = previousMonth(current_month)
        lead = Lead.objects.get(id=1)
        c1 = Consultant.objects.get(id=1)
        c2 = Consultant.objects.get(id=2)
        mission = Mission(lead=lead, subsidiary_id=1, billing_mode="TIME_SPENT", nature="PROD", probability=100)
        mission.save()
        cache.clear()  # avoid bad computation due to rates cache with previous values
        response = self.client.get(reverse("staffing:mission_timesheet", args=[mission.id,]), follow=True, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["margin"], 0)
        self.assertEqual(response.context["objective_margin_total"], 0)
        self.assertEqual(response.context["forecasted_unused"], 0)
        self.assertEqual(response.context["current_unused"], 0)
        self.assertEqual(response.context["avg_daily_rate"], 0)
        # Add some forecast
        Staffing(mission=mission, staffing_date=current_month, consultant=c1, charge=15).save()
        Staffing(mission=mission, staffing_date=current_month, consultant=c2, charge=10).save()
        Staffing(mission=mission, staffing_date=next_month, consultant=c1, charge=8).save()
        Staffing(mission=mission, staffing_date=next_month, consultant=c2, charge=6).save()
        # Add some timesheet - we fake with all charge on the first day
        Timesheet(mission=mission, working_date=previous_month, consultant=c1, charge=8).save()
        Timesheet(mission=mission, working_date=previous_month, consultant=c2, charge=5).save()
        Timesheet(mission=mission, working_date=current_month, consultant=c1, charge=11).save()
        Timesheet(mission=mission, working_date=current_month, consultant=c2, charge=9).save()
        # Define objective rates for consultants
        RateObjective(consultant=c1, start_date=previous_month, rate=700, rate_type="DAILY_RATE").save()
        RateObjective(consultant=c2, start_date=previous_month, rate=1050, rate_type="DAILY_RATE").save()
        # Add financial conditions for this mission
        FinancialCondition(consultant=c1, mission=mission, daily_rate=800).save()
        FinancialCondition(consultant=c2, mission=mission, daily_rate=1100).save()
        # Define mission price
        mission.price = 50
        mission.save()
        # Let's test if computation are rights
        cache.clear()  # avoid bad computation due to rates cache with previous values
        response = self.client.get(reverse("staffing:mission_timesheet", args=[mission.id,]), follow=True, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["margin"], 0)  # That's because we are in timespent
        self.assertEqual(response.context["objective_margin_total"], 4150)
        self.assertEqual(response.context["forecasted_unused"], 2.1)
        self.assertEqual(response.context["current_unused"], 19.4)
        # Switch to fixed price mission
        mission.billing_mode = "FIXED_PRICE"
        mission.save()
        response = self.client.get(reverse("staffing:mission_timesheet", args=[mission.id,]), follow=True, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["margin"], 6.25)
        self.assertEqual(response.context["objective_margin_total"], 4150)
        self.assertEqual(response.context["forecasted_unused"], 2.1)  # Unused is margin on days. Same that timespent
        self.assertEqual(response.context["current_unused"], 19.4)  # idem
        # Check mission data main table
        data = list(response.context["mission_data"])
        self.assertListEqual(data[0], [c2, [5, 9, 14, 15.4], [1, 6, 7, 7.7], [21, 23.1], None, None, None, None])
        self.assertListEqual(data[1], [c1, [8, 11, 19, 15.2], [4, 8, 12, 9.6], [31, 24.8], None, None, None, None])
        self.assertListEqual(data[2], [None, [13, 20, 33, 30.6], [5, 14, 19, 17.3], [52, 47.9],
                                       [11.9, 18.7], [4.3, 13],
                                       [915.4, 935, 927.3], [860, 928.6, 910.5]])

    def test_holiday_csv_timesheet(self):
        #TODO: inject holidays days and timesheet on fixed month with holes and holidays in first and last open days
        self.client.force_login(self.test_user)
        c1 = Consultant.objects.get(id=1)
        # create various holidays missions
        h1 = Mission(nature="HOLIDAYS", description="holiday 1", subsidiary=c1.company)
        h1.save()
        h2 = Mission(nature="HOLIDAYS", description="holiday 2", subsidiary=c1.company)
        h2.save()
        # inject some public holiday
        Holiday(day=date(2023,3,14)).save()
        Holiday(day=date(2023, 3, 24)).save()
        # create some holiday timesheet on this month
        Timesheet(consultant=c1, mission=h1, working_date=date(2023, 3, 1), charge=1).save()
        Timesheet(consultant=c1, mission=h1, working_date=date(2023, 3, 2), charge=0.5).save()
        Timesheet(consultant=c1, mission=h1, working_date=date(2023, 3, 6), charge=1).save()
        Timesheet(consultant=c1, mission=h2, working_date=date(2023, 3, 7), charge=1).save()
        Timesheet(consultant=c1, mission=h1, working_date=date(2023, 3, 10), charge=1).save()
        Timesheet(consultant=c1, mission=h1, working_date=date(2023, 3, 13), charge=1).save()
        Timesheet(consultant=c1, mission=h1, working_date=date(2023, 3, 15), charge=1).save()
        Timesheet(consultant=c1, mission=h1, working_date=date(2023, 3, 23), charge=1).save()
        Timesheet(consultant=c1, mission=h1, working_date=date(2023, 3, 27), charge=1).save()
        Timesheet(consultant=c1, mission=h1, working_date=date(2023, 3, 29), charge=1).save()
        Timesheet(consultant=c1, mission=h1, working_date=date(2023, 3, 30), charge=1).save()
        Timesheet(consultant=c1, mission=h1, working_date=date(2023, 3, 31), charge=1).save()

        response = self.client.get(reverse("staffing:holiday_csv_timesheet", kwargs={"year":2023, "month":3}))
        self.assertEqual(response.status_code, 200)
        r = list(csv.reader(response.content.decode(response.charset).splitlines(), delimiter=";"))
        self.assertEqual([8, 8, 8, 8, 8, 8, 8, 8], [len(i) for i in r])
        self.assertEqual(len(r), 8)
        self.assertEqual(set([i[0] for i in r[1:]]), {c1.trigramme})
        self.assertEqual(sum([float(i[-1]) for i in r[1:]]), 11.5)


class StaffingFormsTest(TestCase):
    fixtures = PYDICI_FIXTURES

    def setUp(self):
        setup_test_user_features()
        self.test_user = User.objects.get(username=TEST_USERNAME)

    def testMissionFormDates(self):
        StaffingFormSet = inlineformset_factory(Mission, Staffing,
                                                formset=MissionStaffingInlineFormset,
                                                form=StaffingForm,
                                                fields="__all__")
        lead = Lead.objects.get(id=1)
        mission = Mission(lead=lead, subsidiary_id=1, billing_mode="TIME_SPENT", nature="PROD", probability=100)
        mission.save()
        c1 = Consultant.objects.get(id=1)
        current_month = date.today().replace(day=1)
        Staffing(mission=mission, staffing_date=current_month, consultant=c1, charge=15).save()

        formset = StaffingFormSet(instance=mission)
        form = formset.forms[0]
        self.assertEqual(form.fields["staffing_date"].choices[-1][0], previousMonth(date.today() + timedelta(days=2*365)))

        end_date = (date.today() + timedelta(days=100)).replace(day=1)
        mission.end_date = end_date
        mission.save()
        formset = StaffingFormSet(instance=mission)
        form = formset.forms[0]
        self.assertEqual(form.fields["staffing_date"].choices[-1][0], end_date)


class OptimTest(TestCase):
    consultants = ["SRE", "JCF", "MFR", "TCO"]
    senior_consultants = ["MFR"]
    director_consultants = ["SRE", "JCF"]
    missions = ["M1", "M2", "M3", "M4"]
    months = ["jan", "feb", "mar"]

    missions_charge = {"M1": {"jan": 25, "feb": 20, "mar": 20},
                       "M2": {"jan": 0, "feb": 0, "mar": 20},
                       "M3": {"jan": 10, "feb": 5, "mar": 0},
                       "M4": {"jan": 5, "feb": 10, "mar": 10},
                       }

    missions_remaining = {"M1": 90000,
                          "M2": 35000,
                          "M3": 30000,
                          "M4": 40000,
                         }

    missions_boundaries = {"M1": {"start": None, "end": None},
                           "M2": {"start": "feb", "end": None},
                           "M3": {"start": None, "end": "mar"},
                           "M4": {"start": None, "end": None}}

    consultants_freetime = {"SRE": {"jan": 15, "feb": 18, "mar": 13},
                            "JCF": {"jan": 10, "feb": 15, "mar": 20},
                            "MFR": {"jan": 20, "feb": 20, "mar": 20},
                            "TCO": {"jan": 20, "feb": 20, "mar": 20},
                            }
    consultants_rates = {"SRE": {"M1": 1500, "M2": 1450, "M3": 1500, "M4": 1800},
                         "JCF": {"M1": 1600, "M2": 1350, "M3": 1500, "M4": 1700},
                         "MFR": {"M1": 1000, "M2": 950, "M3": 1200, "M4": 1400},
                         "TCO": {"M1": 1000, "M2": 950, "M3": 1200, "M4": 1400},
                        }

    predefined_assignment = {"M4": ["JCF", ]}

    exclusions = {"M3": ["JCF", ]}

    def test_optim(self):
        solver, status, scores, staffing = solve_pdc(self.consultants, self.senior_consultants, self.director_consultants,
                                                     self.missions, self.months,
                                                     self.missions_charge, self.missions_remaining, self.missions_boundaries,
                                                     self.consultants_freetime, self.predefined_assignment, self.exclusions,
                                                     self.consultants_rates, solver_param={})
        with mock.patch('sys.stdout', new=StringIO()):
            display_solver_solution(solver, scores, staffing, self.consultants, self.missions, self.months, self.missions_charge, self.consultants_freetime)
        self.assertEqual((sum(solver.Value(score) for score in scores)), 87)
