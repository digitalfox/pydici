# coding: utf-8
"""
Test cases
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

# Python/Django test modules
from django.test import TestCase, override_settings
from django.contrib.auth.models import Group, User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.conf import settings

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromiumService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.utils import ChromeType
from selenium.webdriver.chrome.options import ChromiumOptions


# Pydici modules
from core.utils import monthWeekNumber, previousWeek, nextWeek, cumulateList, capitalize, get_parameter
from core.models import GroupFeature, FEATURES, Parameter

# Python modules used by tests
from datetime import date
import os
import os.path
import sys
from subprocess import Popen, PIPE


TEST_USERNAME = "sre"
PYDICI_PAGES = ("/",
                "/search",
                "/search?q=lala",
                "/leads/1/",
                "/leads/2/",
                "/leads/3/",
                "/admin/",
                "/leads/mail/html",
                "/leads/review",
                "/staffing/pdcreview/",
                "/staffing/pdc_optim/",
                "/staffing/pdcreview/2009/07",
                "/staffing/production-report/",
                "/staffing/production-report/2009/07",
                "/staffing/fixed-price-mission-report/",
                "/staffing/mission/",
                "/staffing/mission/all",
                "/staffing/mission/1/",
                "/staffing/mission/1/#tab-staffing",
                "/staffing/mission/1/#tab-timesheet",
                "/staffing/mission/2/",
                "/staffing/mission/2/#tab-staffing",
                "/staffing/mission/2/#tab-timesheet",
                "/staffing/mission/3/",
                "/staffing/mission/3/#tab-staffing",
                "/staffing/mission/3/#tab-timesheet",
                "/staffing/timesheet/global",
                "/staffing/timesheet/global/?csv",
                "/staffing/timesheet/global/2010/11",
                "/staffing/holidays_report/2010",
                "/staffing/holidays_report/2009",
                "/staffing/holidays_report/all",
                "/staffing/holidays_report/",
                "/staffing/non-prod_report/2010",
                "/staffing/non-prod_report/2009",
                "/staffing/non-prod_report/all",
                "/staffing/non-prod_report/",
                "/staffing/graph/profile-rates/",
                "/staffing/graph/timesheet-rates/",
                "/staffing/mission/1/deactivate",
                "/people/home/consultant/1/",
                "/people/home/consultant/2/",
                "/people/home/consultant/3/",
                "/people/home/consultant/1/#tab-staffing",
                "/people/home/consultant/1/#tab-timesheet",
                "/crm/company/1/detail",
                "/crm/company/all",
                "/billing/graph/billing",
                "/billing/bill_review",
                "/billing/bill_delay",
                "/billing/bill/client/add",
                "/billing/bill/client/archive",
                "/billing/bill/supplier/add",
                "/billing/bill/supplier/archive",
                "/billing/bill/supplier/validation",
                "/risks",
                "/admin/",
                "/admin/crm/",
                "/admin/crm/client/",
                "/admin/crm/subsidiary/",
                "/admin/crm/company/",
                "/admin/crm/contact/",
                "/admin/crm/businessbroker/",
                "/admin/crm/supplier/",
                "/admin/crm/administrativefunction/",
                "/admin/crm/administrativecontact/",
                "/admin/crm/missioncontact/",
                "/admin/crm/clientorganisation/",
                "/admin/leads/",
                "/admin/leads/lead/",
                )

PYDICI_NON_HTML_PAGES = ("/leads/csv/all",
                         "/leads/csv/active",
                         "/leads/mail/text",
                         "/feeds/latest/",
                         "/feeds/mine/",
                         "/feeds/new/",
                         "/feeds/won/",
                         "/feeds/latestStaffing/",
                         "/feeds/myLatestStaffing/",
                         "/feeds/archivedMission/",
                         "/staffing/timesheet/detailed/?",
                         "/staffing/timesheet/detailed/2010/11",
)

PYDICI_AJAX_PAGES = (
                "/staffing/forecast/consultant/1/",
                "/staffing/timesheet/consultant/1/",
                "/staffing/forecast/consultant/1/",
                "/staffing/timesheet/consultant/1/?csv",
                "/staffing/timesheet/consultant/1/2010/10",
                "/staffing/timesheet/consultant/1/2010/10/2",
                "/staffing/timesheet/mission/1/",
                "/staffing/timesheet/mission/1/?csv",
                "/staffing/timesheet/mission/1/?pdf",
                "/staffing/timesheet/mission/1/?csv_grouped",
                "/staffing/forecast/mission/1/",
                "/staffing/missions/consultant/1/",
                "/staffing/missions/consultant/6/",
                "/staffing/mission/1/consultants",
                "/leads/graph/leads-bar",
                "/crm/company/graph/sales",
                "/crm/company/graph/sales/lastyear",
                "/billing/graph/yearly-billing",
)

PYDICI_FIXTURES = ["auth.json", "people.json", "crm.json",
                "leads.json", "staffing.json", "billing.json"]


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class SimpleTest(TestCase):
    fixtures = PYDICI_FIXTURES

    def setUp(self):
        setup_test_user_features()
        self.test_user = User.objects.get(username=TEST_USERNAME)

    def test_basic_page(self):
        self.client.force_login(self.test_user)
        error_msg = "Failed to test url %s (got %s instead of 200)"
        for page in PYDICI_PAGES+PYDICI_NON_HTML_PAGES:
            response = self.client.get(page)
            self.assertEqual(response.status_code, 200, error_msg % (page, response.status_code))
        for page in PYDICI_AJAX_PAGES:
            response = self.client.get(page, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
            self.assertEqual(response.status_code, 200, error_msg % (page, response.status_code))

    def test_page_with_args(self):
        self.client.force_login(self.test_user)
        for page, args in (("/search", {"q": "a"}),
                           ("/search", {"q": "coucou"}),
                           ("/search", {"q": "a+e"})):
            response = self.client.get(page, args)
            self.assertEqual(response.status_code, 200,
                             "Failed to test url %s (got %s instead of 200)" % (page, response.status_code))

    def test_redirect(self):
        self.client.force_login(self.test_user)
        response = self.client.get("/help")
        self.assertEqual(response.status_code, 301)
        for page in ("/staffing/mission/newfromdeal/1/",
                     "/staffing/mission/newfromdeal/2/",
                     "/staffing/forecast/mission/1/",
                     "/staffing/forecast/mission/2/",
                     "/staffing/forecast/mission/3/",
                     "/staffing/timesheet/mission/1/",
                     "/staffing/timesheet/mission/2/",
                     "/staffing/timesheet/mission/3/",
                     "/people/detail/consultant/1/",
                     ):
            response = self.client.get(page)
            self.assertEqual(response.status_code, 302)

    def test_not_found_page(self):
        self.client.force_login(self.test_user)
        for page in ("/leads/234/",
                     "/staffing/mission/5435/"):
            response = self.client.get(page)
            self.assertEqual(response.status_code, 404,
                                 "Failed to test url %s (got %s instead of 404" % (page, response.status_code))

    def test_pdc_review(self):
        self.client.force_login(self.test_user)
        url = "/staffing/pdcreview/2009/07"
        for arg in ({}, {"projected": ""}, {"groupby": "manager"}, {"groupby": "position"},
                    {"n_month": "5"}, {"n_month": "50"}):
            response = self.client.get(url, arg)
            self.assertEqual(response.status_code, 200,
                "Failed to test pdc_review with arg %s (got %s instead of 200" % (arg, response.status_code))


class UtilsTest(TestCase):
    def test_monthWeekNumber(self):
        # Week number, date
        dates = ((1, date(2011, 4, 1)),
                 (1, date(2011, 4, 3)),
                 (2, date(2011, 4, 4)),
                 (2, date(2011, 4, 10)),
                 (5, date(2011, 4, 30)))
        for weekNum, weekDate in dates:
            self.assertEqual(weekNum, monthWeekNumber(weekDate))

    def test_previousWeek(self):
        # Previous week first day, week day
        dates = ((date(2011, 3, 28), date(2011, 4, 1)),
                 (date(2011, 3, 28), date(2011, 4, 2)),
                 (date(2011, 3, 28), date(2011, 4, 3)),
                 (date(2011, 4, 1), date(2011, 4, 4)),
                 (date(2011, 4, 1), date(2011, 4, 10)),
                 (date(2011, 4, 18), date(2011, 4, 30)),
                 (date(2010, 12, 27), date(2011, 1, 1)),
                 (date(2010, 12, 27), date(2011, 1, 2)),
                 (date(2011, 1, 1), date(2011, 1, 3)),
                 )
        for firstDay, weekDay in dates:
            self.assertEqual(firstDay, previousWeek(weekDay))

    def test_nextWeek(self):
        # Previous week first day, week day
        dates = ((date(2011, 4, 4), date(2011, 4, 1)),
                 (date(2011, 4, 4), date(2011, 4, 2)),
                 (date(2011, 4, 4), date(2011, 4, 3)),
                 (date(2011, 4, 11), date(2011, 4, 4)),
                 (date(2011, 4, 11), date(2011, 4, 10)),
                 (date(2011, 5, 1), date(2011, 4, 30)),
                 (date(2011, 5, 2), date(2011, 5, 1)),
                 (date(2011, 1, 1), date(2010, 12, 31)),
                 (date(2011, 1, 3), date(2011, 1, 1)),
                 (date(2011, 1, 3), date(2011, 1, 2)),
                 (date(2011, 1, 10), date(2011, 1, 3)),
                 )
        for firstDay, weekDay in dates:
            self.assertEqual(firstDay, nextWeek(weekDay))

    def test_cumulateList(self):
        self.assertListEqual(cumulateList([1, 2, 3]), [1, 3, 6])
        self.assertListEqual(cumulateList([]), [])
        self.assertListEqual(cumulateList([8]), [8])

    def test_capitalize(self):
        data = (("coucou", "Coucou"),
                ("état de l'art", "État De L'Art"),
                ("fusion du si", "Fusion Du Si"),
                ("cohérence du SI", "Cohérence Du SI"),
                ("test-and-learn", "Test-And-Learn"))
        for word, capitalizeddWord in data:
            self.assertEqual(capitalizeddWord, capitalize(word))


    def test_parameter(self):
        self.assertRaises(Exception, get_parameter, "foo")
        p = Parameter(key="testT", value="valueT", type="TEXT", desc="test")
        p.save()
        self.assertEqual(get_parameter(p.key), p.value)
        p = Parameter(key="testF", value=0.666, type="FLOAT", desc="test")
        p.save()
        self.assertEqual(get_parameter(p.key), p.value)
        p.value=0.777
        p.save()
        self.assertEqual(get_parameter(p.key), p.value)


class SeleniumTestCase(StaticLiveServerTestCase):
    """Parent class of Selenium based tests"""
    def setUp(self):
        options = ChromiumOptions()
        options.headless = True
        options.add_argument("--no-sandbox")
        self.driver = webdriver.Chrome(
            service=ChromiumService(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()), options=options)

    def tearDown(self):
        self.driver.close()

class SimpleJsTest(SeleniumTestCase):
    """Test page through selenium to check that javascript stuff is going well"""
    serialized_rollback = True
    fixtures = PYDICI_FIXTURES

    def test_missing_resource_and_js_errors(self):
        setup_test_user_features()
        urls = [self.live_server_url + page for page in PYDICI_PAGES]
        self.test_user = User.objects.get(username=TEST_USERNAME)
        self.client.force_login(self.test_user)
        cookie_name = settings.SESSION_COOKIE_NAME
        self.driver.get(urls[0])  # Need to init driver on a domain before setting cookie
        self.driver.get_log("browser")  # pop error log
        self.driver.add_cookie({"name": cookie_name, "value": self.client.cookies[cookie_name].value})
        for url in urls:
            self.driver.get(url)
            for log in self.driver.get_log("browser"):
                self.assertNotEqual(log["level"], "SEVERE",
                                    f"JS error on {url}\nsource {log['source']}\n{log['message']}")
                # print(self.driver.page_source)


def setup_test_user_features():
    admin_group = Group(name="admin")
    admin_group.save()
    for name in FEATURES:
        GroupFeature(feature=name, group=admin_group).save()

    test_user = User.objects.get(username=TEST_USERNAME)
    test_user.groups.add(admin_group)
    test_user.save()
