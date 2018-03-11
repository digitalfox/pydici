# -*- coding: UTF-8 -*-
"""URL dispatcher for CRM module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import patterns, url

from crm import views as v
from crm import tables as t

crm_urls = patterns('crm.views',
                    url(r'^contact/add/$', v.ContactCreate.as_view(), name='contact_add'),
                    url(r'^contact/(?P<pk>\d+)/update$', v.ContactUpdate.as_view(), name='contact_update'),
                    url(r'^mission/contact/add/$', v.MissionContactCreate.as_view(), name='mission_contact_add'),
                    url(r'^mission/contact/(?P<pk>\d+)/update$', v.MissionContactUpdate.as_view(), name='mission_contact_update'),
                    url(r'^businessbroker/add/$', v.BusinessBrokerCreate.as_view(), name='businessbroker_add'),
                    url(r'^businessbroker/(?P<pk>\d+)/update$', v.BusinessBrokerUpdate.as_view(), name='businessbroker_update'),
                    url(r'^supplier/add/$', v.SupplierCreate.as_view(), name='supplier_add'),
                    url(r'^supplier/(?P<pk>\d+)/update$', v.SupplierUpdate.as_view(), name='supplier_update'),
                    url(r'^administrative/contact/add/$', v.AdministrativeContactCreate.as_view(), name='administrative_contact_add'),
                    url(r'^administrative/contact/(?P<pk>\d+)/update$', v.AdministrativeContactUpdate.as_view(), name='administrative_contact_update'),
                    url(r'contact/(?P<pk>\d+)/delete/$', v.ContactDelete.as_view(), name='contact_delete'),
                    url(r'contact/(?P<pk>\d+)/$', v.ContactDetail.as_view(), name='contact_detail'),
                    url(r'contact/all/$', "contact_list", name='contact_list'),
                    url(r'contact/datatable/data/$', t.ContactTableDT.as_view(), name='all_contacts_table_DT'),
                    url(r'^company/(?P<company_id>\d+)/detail$', 'company_detail', name="company_detail"),
                    url(r'^company/(?P<company_id>\d+)/rates-margin$', 'company_rates_margin', name="company_rates_margin"),
                    url(r'^company/(?P<company_id>\d+)/billing$', 'company_billing', name="company_billing"),
                    url(r'^company/(?P<company_id>\d+)/pivotable$', 'company_pivotable', name="company-pivotable"),
                    (r'^company/all$', 'company_list'),
                    (r'^company$', 'company'),
                    (r'^company/(?P<company_id>\d+)/change$', 'company'),
                    (r'^client$', 'client'),
                    url(r'^client/(?P<client_id>\d+)/change$', 'client', name="client_change"),
                    (r'^client-organisation$', 'clientOrganisation'),
                    (r'^client-organisation/(?P<client__organisation_id>\d+)/change$', 'clientOrganisation'),
                    url(r'^company/graph/sales$', 'graph_company_sales', name="graph_company_sales"),
                    url(r'^company/graph/sales/lastyear$', 'graph_company_sales', {"onlyLastYear": True}, name="graph_company_lastyear_sales"),
                    url(r'^company/graph/sales/lastyear/(?P<subsidiary_id>[0-9]+)$', 'graph_company_sales', {"onlyLastYear": True}, name="graph_company_lastyear_sales"),
                    url(r'^company/(?P<company_id>\d+)/graph/business_activity$', 'graph_company_business_activity', name="graph_company_business_activity"),
                    (r'^client-organisation-company-popup$', 'client_organisation_company_popup'),
                    )
