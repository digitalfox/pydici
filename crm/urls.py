# -*- coding: UTF-8 -*-
"""URL dispatcher for CRM module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.urls import re_path

from crm import views as v
from crm import tables as t

crm_urls = [
             re_path(r'^contact/add/$', v.ContactCreate.as_view(), name='contact_create'),
             re_path(r'^contact/(?P<pk>\d+)/update$', v.ContactUpdate.as_view(), name='contact_update'),
             re_path(r'^mission/contact/add/$', v.MissionContactCreate.as_view(), name='mission_contact_create'),
             re_path(r'^mission/contact/(?P<pk>\d+)/update$', v.MissionContactUpdate.as_view(), name='mission_contact_update'),
             re_path(r'^businessbroker/add/$', v.BusinessBrokerCreate.as_view(), name='businessbroker_create'),
             re_path(r'^businessbroker/(?P<pk>\d+)/update$', v.BusinessBrokerUpdate.as_view(), name='businessbroker_update'),
             re_path(r'^businessbroker/all/$', v.businessbroker_list, name='businessbroker_list'),
             re_path(r'^businessbroker/datatable/data/$', t.BusinessBrokerTableDT.as_view(), name='all_businessbroker_table_DT'),
             re_path(r'^supplier/add/$', v.SupplierCreate.as_view(), name='supplier_create'),
             re_path(r'^supplier/(?P<pk>\d+)/update$', v.SupplierUpdate.as_view(), name='supplier_update'),
             re_path(r'^supplier/all/$', v.supplier_list, name='supplier_list'),
             re_path(r'^supplier/datatable/data/$', t.SupplierTableDT.as_view(), name='all_supplier_table_DT'),
             re_path(r'^administrative/contact/add/$', v.AdministrativeContactCreate.as_view(), name='administrative_contact_add'),
             re_path(r'^administrative/contact/(?P<pk>\d+)/update$', v.AdministrativeContactUpdate.as_view(), name='administrative_contact_update'),
             re_path(r'contact/(?P<pk>\d+)/delete/$', v.ContactDelete.as_view(), name='contact_delete'),
             re_path(r'contact/(?P<pk>\d+)/$', v.ContactDetail.as_view(), name='contact_detail'),
             re_path(r'contact/all/$', v.contact_list, name='contact_list'),
             re_path(r'contact/datatable/data/$', t.ContactTableDT.as_view(), name='all_contacts_table_DT'),
             re_path(r'^company/(?P<company_id>\d+)/detail$', v.company_detail, name="company_detail"),
             re_path(r'^company/(?P<company_id>\d+)/rates-margin$', v.company_rates_margin, name="company_rates_margin"),
             re_path(r'^company/(?P<company_id>\d+)/billing$', v.company_billing, name="company_billing"),
             re_path(r'^company/(?P<company_id>\d+)/pivotable$', v.company_pivotable, name="company_pivotable"),
             re_path(r'^company/all$', v.company_list, name="company_list"),
             re_path(r'^company$', v.company, name="company"),
             re_path(r'^company/(?P<company_id>\d+)/change$', v.company, name="company"),
             re_path(r'^client$', v.client, name="client"),
             re_path(r'^client/(?P<client_id>\d+)/change$', v.client, name="client_change"),
             re_path(r'^client-organisation$', v.clientOrganisation, name="client_organisation"),
             re_path(r'^client-organisation/(?P<client_organisation_id>\d+)/change$', v.clientOrganisation, name="client_organisation_change"),
             re_path(r'^clients/ranking$', v.clients_ranking, name="clients_ranking"),
             re_path(r'^company/graph/sales$', v.graph_company_sales, name="graph_company_sales"),
             re_path(r'^company/graph/sales/(?P<subsidiary_id>[0-9]+)$$', v.graph_company_sales, name="graph_company_sales"),
             re_path(r'^company/graph/sales/lastyear$', v.graph_company_sales, {"onlyLastYear": True}, name="graph_company_lastyear_sales"),
             re_path(r'^company/graph/sales/lastyear/(?P<subsidiary_id>[0-9]+)$', v.graph_company_sales, {"onlyLastYear": True}, name="graph_company_lastyear_sales"),
             re_path(r'^company/(?P<company_id>\d+)/graph/business_activity$', v.graph_company_business_activity, name="graph_company_business_activity"),
             re_path(r'^client-organisation-company-popup$', v.client_organisation_company_popup, name="client_organisation_company_popup"),
            ]
