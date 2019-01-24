# -*- coding: UTF-8 -*-
"""URL dispatcher for CRM module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import url

from crm import views as v
from crm import tables as t

crm_urls = [
            url(r'^contact/add/$', v.ContactCreate.as_view(), name='contact_create'),
            url(r'^contact/(?P<pk>\d+)/update$', v.ContactUpdate.as_view(), name='contact_update'),
            url(r'^mission/contact/add/$', v.MissionContactCreate.as_view(), name='mission_contact_create'),
            url(r'^mission/contact/(?P<pk>\d+)/update$', v.MissionContactUpdate.as_view(), name='mission_contact_update'),
            url(r'^businessbroker/add/$', v.BusinessBrokerCreate.as_view(), name='businessbroker_create'),
            url(r'^businessbroker/(?P<pk>\d+)/update$', v.BusinessBrokerUpdate.as_view(), name='businessbroker_update'),
            url(r'^supplier/add/$', v.SupplierCreate.as_view(), name='supplier_create'),
            url(r'^supplier/(?P<pk>\d+)/update$', v.SupplierUpdate.as_view(), name='supplier_update'),
            url(r'^administrative/contact/add/$', v.AdministrativeContactCreate.as_view(), name='administrative_contact_add'),
            url(r'^administrative/contact/(?P<pk>\d+)/update$', v.AdministrativeContactUpdate.as_view(), name='administrative_contact_update'),
            url(r'contact/(?P<pk>\d+)/delete/$', v.ContactDelete.as_view(), name='contact_delete'),
            url(r'contact/(?P<pk>\d+)/$', v.ContactDetail.as_view(), name='contact_detail'),
            url(r'contact/all/$', v.contact_list, name='contact_list'),
            url(r'contact/datatable/data/$', t.ContactTableDT.as_view(), name='all_contacts_table_DT'),
            url(r'^company/(?P<company_id>\d+)/detail$', v.company_detail, name="company_detail"),
            url(r'^company/(?P<company_id>\d+)/rates-margin$', v.company_rates_margin, name="company_rates_margin"),
            url(r'^company/(?P<company_id>\d+)/billing$', v.company_billing, name="company_billing"),
            url(r'^company/(?P<company_id>\d+)/pivotable$', v.company_pivotable, name="company_pivotable"),
            url(r'^company/all$', v.company_list, name="company_list"),
            url(r'^company$', v.company, name="company"),
            url(r'^company/(?P<company_id>\d+)/change$', v.company, name="company"),
            url(r'^client$', v.client, name="client"),
            url(r'^client/(?P<client_id>\d+)/change$', v.client, name="client_change"),
            url(r'^client-organisation$', v.clientOrganisation, name="client_organisation"),
            url(r'^client-organisation/(?P<client_organisation_id>\d+)/change$', v.clientOrganisation, name="client_organisation_change"),
            url(r'^company/graph/sales$', v.graph_company_sales, name="graph_company_sales"),
            url(r'^company/graph/sales/lastyear$', v.graph_company_sales, {"onlyLastYear": True}, name="graph_company_lastyear_sales"),
            url(r'^company/graph/sales/lastyear/(?P<subsidiary_id>[0-9]+)$', v.graph_company_sales, {"onlyLastYear": True}, name="graph_company_lastyear_sales"),
            url(r'^company/(?P<company_id>\d+)/graph/business_activity$', v.graph_company_business_activity, name="graph_company_business_activity"),
            url(r'^client-organisation-company-popup$', v.client_organisation_company_popup, name="client_organisation_company_popup"),
            ]
