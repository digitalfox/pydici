# -*- coding: UTF-8 -*-
"""URL dispatcher for billing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.urls import re_path

import billing.views as v
import billing.tables as t


billing_urls = [ re_path(r'^bill_review$', v.bill_review, name="bill_review"),
                 re_path(r'^client_billing_control$', v.client_billing_control_pivotable, name='client_billing_control_pivotable'),
                 re_path(r'^bill_delay$', v.bill_delay, name="bill_delay"),
                 re_path(r'^bill/(?P<bill_id>\d+)/mark_bill_paid$', v.mark_bill_paid, name="mark_bill_paid"),
                 re_path(r'^file/(?P<nature>.+)/(?P<bill_id>\d+)$', v.bill_file, name="bill_file"),
                 re_path(r'^pdf/(?P<bill_id>\d+)$', v.BillPdf.as_view(), name="bill_pdf"),
                 re_path(r'^html/(?P<bill_id>\d+)$', v.Bill.as_view(), name="bill_html"),
                 re_path(r'^bill/client/add$', v.client_bill, name='client_bill'),
                 re_path(r'^bill/client/(?P<bill_id>\d+)/edit$', v.client_bill, name='client_bill'),
                 re_path(r'^bill/client/(?P<bill_id>\d+)/delete$', v.clientbill_delete, name='clientbill_delete'),
                 re_path(r'^bill/client/(?P<bill_id>\d+)/detail$', v.client_bill_detail, name='client_bill_detail'),
                 re_path(r'^bill/client/creation$', v.client_bills_in_creation, name='client_bills_in_creation'),
                 re_path(r'^bill/client/archive$', v.client_bills_archive, name='client_bills_archive'),
                 re_path(r'^bill/supplier/add$', v.supplier_bill, name='supplier_bill'),
                 re_path(r'^bill/supplier/(?P<bill_id>\d+)$', v.supplier_bill, name='supplier_bill'),
                 re_path(r'^bill/supplier/(?P<bill_id>\d+)/delete$', v.supplierbill_delete, name='supplierbill_delete'),
                 re_path(r'^bill/supplier/(?P<bill_id>\d+)/validate$', v.validate_supplier_bill, name="validate_supplier_bill"),
                 re_path(r'^bill/supplier/(?P<bill_id>\d+)/mark_bill_paid$', v.mark_supplierbill_paid, name="mark_supplierbill_paid"),
                 re_path(r'^bill/supplier/archive$', v.supplier_bills_archive, name='supplier_bills_archive'),
                 re_path(r'^bill/supplier/validation$', v.supplier_bills_validation, name="supplier_bills_validation"),
                 re_path(r'^pre_billing/$', v.pre_billing, {"mine": False, }, name="pre_billing"),
                 re_path(r'^pre_billing/mine/$', v.pre_billing, {"mine": True, }, name="pre_billing"),
                 re_path(r'^pre_billing/(?P<start_date>\d{6})/(?P<end_date>\d{6})/?$', v.pre_billing, {"mine": False, }, name="pre_billing"),
                 re_path(r'^pre_billing/mine/(?P<start_date>\d{6})/(?P<end_date>\d{6})/?$', v.pre_billing, {"mine": True, }, name="pre_billing"),
                 re_path(r'lead_blling/(?P<lead_id>\d+)$', v.lead_billing, name="lead_billing"),
                 re_path(r'^datatable/client_bills_in_creation/data/$', t.ClientBillInCreationTableDT.as_view(), name='client_bills_in_creation_DT'),
                 re_path(r'^datatable/client_bills_archive/data/$', t.ClientBillArchiveTableDT.as_view(), name='client_bills_archive_DT'),
                 re_path(r'^datatable/(?P<company_id>\d+)/client_bills_archive/data/$', t.ClientBillArchiveTableDT.as_view(), name='client_company_bills_archive_DT'),
                 re_path(r'^datatable/supplier_bills_archive/data/$', t.SupplierBillArchiveTableDT.as_view(), name='supplier_bills_archive_DT'),
                 re_path(r'^datatable/(?P<company_id>\d+)/supplier_bills_archive/data/$', t.SupplierBillArchiveTableDT.as_view(), name='client_supplier_bills_archive_DT'),
                 re_path(r'^graph/billing$', v.graph_billing, name="graph_billing"),
                 re_path(r'^graph/yearly-billing$', v.graph_yearly_billing, name="graph_yearly_billing"),
                 re_path(r'^graph/outstanding-billing$', v.graph_outstanding_billing, name="graph_outstanding_billing"),
                ]
