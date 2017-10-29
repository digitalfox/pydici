# coding: utf-8
"""
Test cases for CRM module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.test import TestCase
from django.core import urlresolvers
from django.contrib.auth.models import Group, User

from crm.models import Client, Subsidiary
from people.models import Consultant, ConsultantProfile
from staffing.models import Mission
from core.tests import PYDICI_FIXTURES, setup_test_user_features, TEST_USERNAME, TEST_PASSWORD

import json


class CrmViewsTest(TestCase):
    fixtures = PYDICI_FIXTURES

    def setUp(self):
        setup_test_user_features()

    def test_client_all_in_one(self):
        self.client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
        view = urlresolvers.reverse("crm.views.client_organisation_company_popup")
        error_tag = "form-group has-error"

        # Initial data
        data = { "client-expectations": "3_FLAT",
                 "client-alignment": "2_STANDARD",
                 "client-contact": "",
                 "contact-name": "",
                 "contact-email": "",
                 "contact-function": "",
                 "contact-mobile_phone": "",
                 "contact-phone": "",
                 "contact-fax": "",
                 "organisation-name": "",
                 "company-name": "",
                 "company-code": "",
                 "company-web": "" }

        # Remove existing client that we will create
        Client.objects.get(id=1).delete()

        # Incomplete form with initial data
        response = self.client.post(view, data=data, follow=True)
        self.check_client_popup_response_is_ko(response)

        # Simple form with existing organisation
        data["client-organisation"] = 1
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response)
        client.delete()

        # Same with existing contact
        data["client-contact"] = 1
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response)
        self.assertEqual(client.contact.id, 1)
        client.delete()

        # Same with a new contact, but incomplete
        del data["client-contact"]
        data["contact-mail"] = "Joe@worldcompany.com"
        response = self.client.post(view, data=data, follow=True)
        # Yes it works. We cannot distinguish incomplete contact and no contact, so, incomplete contact is ignored
        client = self.check_client_popup_response_is_ok(response)
        client.delete()

        # And now with a complete new contact
        data["contact-name"] = "Joe"
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response)
        self.assertEquals(client.contact.name, "Joe")
        client.delete()

        # Time to create organisation with existing company
        del data["client-organisation"]
        data["organisation-name"] = "blabla"
        data["organisation-company"] = 1
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response)
        self.assertEquals(client.organisation.name, "blabla")
        self.assertEquals(client.organisation.company.id, 1)
        client.delete()

        # Incomplete new organisation should fail
        del data["organisation-name"]
        response = self.client.post(view, data=data, follow=True)
        self.check_client_popup_response_is_ko(response)

        # Incomplete new company should fail
        del data["organisation-company"]
        data["organisation-name"] = "youpala"
        data["company-name"] = "The youpala company"
        response = self.client.post(view, data=data, follow=True)
        self.check_client_popup_response_is_ko(response)

        # All-in. Create new organisation and a new company with a new contact
        data["company-code"] = "YOU"
        data["company-businessOwner"] = 1
        data["contact-name"] = "Superman"
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response)
        self.assertEquals(client.organisation.name, "youpala")
        self.assertEquals(client.organisation.company.code, "YOU")
        self.assertEquals(client.contact.name, "Superman")


    def check_client_popup_response_is_ok(self, response):
        """Ensure POST form is ok and return created client"""
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data["success"])
        # self.assertNotIn(error_tag, response_data["form"])
        self.assertIn("client_id", response_data)
        self.assertIn("client_name", response_data)
        return Client.objects.get(id=int(response_data["client_id"]))

    def check_client_popup_response_is_ko(self, response):
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertFalse(response_data["success"])
        # self.assertIn(error_tag, response_data["form"])


class CrmModelTest(TestCase):
    fixtures = PYDICI_FIXTURES

    def test_people_consultant_save(self):
        c = Consultant()
        c.company = Subsidiary.objects.get(id=1)
        c.profil = ConsultantProfile.objects.get(id=1)
        c.name = "john doe"
        c.trigramme = "jdo"
        c.save()
        self.assertEqual(c.name, "John Doe")
        self.assertEqual(c.trigramme, "JDO")

    def test_people_consultant_active_missions(self):
        c = Consultant.objects.get(trigramme="SRE")
        self.assertEqual(list(c.active_missions()), list(Mission.objects.filter(id=1)))

    def test_getUser(self):
        c = Consultant.objects.get(trigramme="SRE")
        u = User.objects.get(username="sre")
        self.assertEqual(c.getUser(), u)
        c = Consultant.objects.get(trigramme="GBA")
        self.assertEqual(c.getUser(), None)

    def test_team(self):
        c = Consultant.objects.get(trigramme="SRE")
        self.assertEqual(list(c.team().order_by("id").values_list("id", flat=True)), [3, 5])
        self.assertEqual(list(c.team(excludeSelf=False).order_by("id").values_list("id", flat=True)), [1, 3, 5])
        self.assertEqual(list(c.team(excludeSelf=False, onlyActive=True).order_by("id").values_list("id", flat=True)), [1, 5])
        self.assertEqual(list(c.team(onlyActive=True).order_by("id").values_list("id", flat=True)), [5, ])

    def test_user_team(self):
        c = Consultant.objects.get(trigramme="SRE")
        self.assertEqual(c.userTeam(), [User.objects.get(username="abr"), None])
        self.assertEqual(c.userTeam(excludeSelf=False), [User.objects.get(username="abr"), None, User.objects.get(username="sre")])

    def test_pending_action(self):
        c = Consultant.objects.get(trigramme="SRE")
        self.assertQuerysetEqual(c.pending_actions(), [])

