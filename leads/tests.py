# coding: utf-8
"""
Test cases
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: BSD
"""

# Python/Django test modules
from django.test import TestCase

# Pydici modules
from pydici.leads.models import Consultant, Client, Lead

# Python modules used by tests
from urllib2 import urlparse

class SimpleTest(TestCase):
    fixtures = ["auth.json", "contenttypes.json", "leads.json"]
    def test_basic_page(self):
        self.client.login(username='sre', password='rototo')
        for page in ("/leads/",
                     "/leads/3/",
                     "/leads/25/",
                     "/leads/admin/",
                     "/leads/csv/all",
                     "/leads/csv/active",
                     "/leads/sendmail/4/",
                     "/leads/mail/text",
                     "/leads/mail/html",
                     "/leads/review",
                     "/leads/feeds/latest/",
                     "/leads/feeds/mine/",
                     "/leads/feeds/new/",
                     "/leads/feeds/won/"):
            response = self.client.get(page)
            self.failUnlessEqual(response.status_code, 200,
                                 "Failed to test url %s (got %s instead of 200" % (page, response.status_code))

    def test_not_found_page(self):
        self.client.login(username='sre', password='rototo')
        for page in ("/leads/234/",
                     "/leads/sendmail/434/"):
            response = self.client.get(page)
            self.failUnlessEqual(response.status_code, 404,
                                 "Failed to test url %s (got %s instead of 404" % (page, response.status_code))

    def test_create_lead(self):
        self.client.login(username='sre', password='rototo')
        lead=Lead(name="laala",
                  due_date="2008-11-01",
                  update_date="2008-11-01 16:14:16",
                  creation_date="2008-11-01 15:43:43",
                  start_date="2008-11-01",
                  responsible=None,
                  sales=None,
                  external_staffing="JCF",
                  salesId="A6code",
                  state="QUALIF",
                  client=Client.objects.get(pk=3),
                  salesman=None, 
                  description="A wonderfull lead that as a so so long description")

        lead.save()
        self.failUnlessEqual(lead.staffing.count(), 0)
        lead.staffing.add(Consultant.objects.get(pk=1))
        self.failUnlessEqual(lead.staffing.count(), 1)
        # Add staffing here lead.add...
        self.failUnlessEqual(len(lead.update_date_strf()), 14)
        self.failUnlessEqual(lead.staffing_list(), "SRE, JCF")
        self.failUnlessEqual(lead.short_description(), "A wonderfull lead th...")
        self.failUnlessEqual(lead.get_absolute_url(), "http://localhost:8000/leads/41/")
        
        url="".join(urlparse.urlsplit(lead.get_absolute_url())[2:])
        response = self.client.get(url)
        self.failUnlessEqual(response.status_code, 200)
        context = response.context[-1]
        self.failUnlessEqual(unicode(context["lead"]), u"laala (RTE : DSI )")
        self.failUnlessEqual(unicode(context["user"]), "sre")

