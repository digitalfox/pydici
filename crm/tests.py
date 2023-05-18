# coding: utf-8
"""
Test cases for CRM module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import Group, User

from crm.models import Client, Subsidiary
from people.models import Consultant, ConsultantProfile
from staffing.models import Mission
from core.tests import PYDICI_FIXTURES, setup_test_user_features, TEST_USERNAME

import json


class CrmViewsTest(TestCase):
    fixtures = PYDICI_FIXTURES

    def setUp(self):
        setup_test_user_features()
        self.test_user = User.objects.get(username=TEST_USERNAME)

    def test_client_all_in_one(self):
        self.client.force_login(self.test_user)
        view = reverse("crm:client_organisation_company_popup")
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
                 "organisation-billing_lang": "fr-fr",
                 "company-name": "",
                 "company-code": "",
                 "company-web": "",
                 "company-business_sector": "1"}

        # Remove existing client that we will create
        Client.objects.get(id=1).delete()

        # Incomplete form with initial data
        response = self.client.post(view, data=data, follow=True)
        self.check_client_popup_response_is_ko(response, "Incomplete form with initial data")

        # Simple form with existing organisation
        data["client-organisation"] = 1
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response, "Simple form with existing organisation")
        client.delete()

        # Same with existing contact
        data["client-contact"] = 1
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response, "Same with existing contact")
        self.assertEqual(client.contact.id, 1, "Same with existing contact")
        client.delete()

        # Same with a new contact, but incomplete
        del data["client-contact"]
        data["contact-mail"] = "Joe@worldcompany.com"
        response = self.client.post(view, data=data, follow=True)
        # Yes it works. We cannot distinguish incomplete contact and no contact, so, incomplete contact is ignored
        client = self.check_client_popup_response_is_ok(response, "Same with a new contact, but incomplete")
        client.delete()

        # And now with a complete new contact
        data["contact-name"] = "Joe"
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response, "And now with a complete new contact")
        self.assertEqual(client.contact.name, "Joe", "And now with a complete new contact")
        client.delete()

        # Time to create organisation with existing company
        del data["client-organisation"]
        data["organisation-name"] = "blabla"
        data["organisation-company"] = 1
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response, "Time to create organisation with existing company")
        self.assertEqual(client.organisation.name, "blabla", "Time to create organisation with existing company")
        self.assertEqual(client.organisation.company.id, 1, "Time to create organisation with existing company")
        client.delete()

        # Incomplete new organisation should fail
        del data["organisation-name"]
        response = self.client.post(view, data=data, follow=True)
        self.check_client_popup_response_is_ko(response, "Incomplete new organisation should fail")

        # Incomplete new company should fail
        del data["organisation-company"]
        data["organisation-name"] = "youpala"
        data["company-name"] = "The youpala company"
        response = self.client.post(view, data=data, follow=True)
        self.check_client_popup_response_is_ko(response, "Incomplete new company should fail")

        # All-in. Create new organisation and a new company with a new contact
        data["company-code"] = "YOU"
        data["company-businessOwner"] = 1
        data["contact-name"] = "Superman"
        response = self.client.post(view, data=data, follow=True)
        client = self.check_client_popup_response_is_ok(response, "All-in. Create new organisation and a new company with a new contact")
        self.assertEqual(client.organisation.name, "youpala", "All-in. Create new organisation and a new company with a new contact")
        self.assertEqual(client.organisation.company.code, "YOU", "All-in. Create new organisation and a new company with a new contact")
        self.assertEqual(client.contact.name, "Superman", "All-in. Create new organisation and a new company with a new contact")


    def check_client_popup_response_is_ok(self, response, msg):
        """Ensure POST form is ok and return created client"""
        self.assertEqual(response.status_code, 200, msg)
        response_data = json.loads(response.content)
        self.assertTrue(response_data["success"], msg)
        self.assertIn("client_id", response_data, msg)
        self.assertIn("client_name", response_data, msg)
        return Client.objects.get(id=int(response_data["client_id"]))

    def check_client_popup_response_is_ko(self, response, msg):
        self.assertEqual(response.status_code, 200, msg)
        response_data = json.loads(response.content)
        self.assertFalse(response_data["success"], msg)


class CrmModelTest(TestCase):
    fixtures = PYDICI_FIXTURES
