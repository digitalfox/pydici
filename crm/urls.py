# -*- coding: UTF-8 -*-
"""URL dispatcher for CRM module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import patterns, url

from crm import views as v

crm_urls = patterns('crm.views',
                    url(r'^contact/add/$', v.ContactCreate.as_view(), name='contact_add'),
                    url(r'^contact/(?P<pk>\d+)/update$', v.ContactUpdate.as_view(), name='contact_update'),
                    url(r'^mission/contact/add/$', v.MissionContactCreate.as_view(), name='mission_contact_add'),
                    url(r'^mission/contact/(?P<pk>\d+)/update$', v.MissionContactUpdate.as_view(), name='mission_contact_update'),
                    url(r'contact/(?P<pk>\d+)/delete/$', v.ContactDelete.as_view(), name='contact_delete'),
                    url(r'contact/(?P<pk>\d+)/$', v.ContactDetail.as_view(), name='contact_detail'),
                    url(r'contact/all/$', v.ContactList.as_view(), name='contact_list'),
                    (r'^company/(?P<company_id>\d+)/detail$', 'company_detail'),
                    (r'^company/all$', 'company_list'),
                    (r'^company$', 'company'),
                    (r'^company/(?P<company_id>\d+)/change$', 'company'),
                    (r'^client$', 'client'),
                    (r'^client/(?P<client_id>\d+)/change$', 'client'),
                    (r'^client-organisation$', 'clientOrganisation'),
                    (r'^client-organisation/(?P<client__organisation_id>\d+)/change$', 'clientOrganisation'),
                    url(r'^company/graph/sales$', 'graph_company_sales_jqp', name="graph_company_sales"),
                    url(r'^company/graph/sales/lastyear$', 'graph_company_sales_jqp', {"onlyLastYear": True}, name="graph_company_lastyear_sales"),
                    url(r'^company/(?P<company_id>\d+)/graph/business_activity$', 'graph_company_business_activity_jqp', name="graph_company_business_activity"),
                    )
