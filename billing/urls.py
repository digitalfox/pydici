# -*- coding: UTF-8 -*-
"""URL dispatcher for billing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import url

import billing.views as v
import billing.tables as t


billing_urls = [url(r'^bill_review', v.bill_review, name="bill_review"),
                url(r'^client_billing_control$', v.client_billing_control_pivotable, name='client_billing_control_pivotable'),
                url(r'^bill_delay', v.bill_payment_delay, name="bill_payment_delay"),
                url(r'^bill/(?P<bill_id>\d+)/mark_bill_paid$', v.mark_bill_paid, name="mark_bill_paid"),
                url(r'^file/(?P<nature>.+)/(?P<bill_id>\d+)$', v.bill_file, name="bill_file"),
                url(r'^pdf/(?P<bill_id>\d+)$', v.BillPdf.as_view(), name="bill_pdf"),
                url(r'^html/(?P<bill_id>\d+)$', v.Bill.as_view(), name="bill_html"),
                url(r'^bill/client/add$', v.client_bill, name='client_bill'),
                url(r'^bill/client/(?P<bill_id>\d+)$', v.client_bill, name='client_bill'),
                url(r'^bill/client/(?P<bill_id>\d+)/delete$', v.clientbill_delete, name='clientbill_delete'),
                url(r'^bill/client/creation$', v.client_bills_in_creation, name='client_bills_in_creation'),
                url(r'^bill/client/archive$', v.client_bills_archive, name='client_bills_archive'),
                url(r'^bill/supplier/add$', v.supplier_bill, name='supplier_bill'),
                url(r'^bill/supplier/(?P<bill_id>\d+)$', v.supplier_bill, name='supplier_bill'),
                url(r'^bill/supplier/(?P<bill_id>\d+)/delete$', v.supplierbill_delete, name='supplierbill_delete'),
                url(r'^bill/supplier/(?P<bill_id>\d+)/validate$', v.validate_supplier_bill, name="validate_supplier_bill"),
                url(r'^bill/supplier/(?P<bill_id>\d+)/mark_bill_paid$', v.mark_supplierbill_paid, name="mark_supplierbill_paid"),
                url(r'^bill/supplier/archive$', v.supplier_bills_archive, name='supplier_bills_archive'),
                url(r'^pre_billing$', v.pre_billing, {"mine": False, }, name="pre_billing"),
                url(r'^pre_billing/mine$', v.pre_billing, {"mine": True, }, name="pre_billing"),
                url(r'^pre_billing/(?P<start_date>\d{6})/(?P<end_date>\d{6})/?$', v.pre_billing, {"mine": False, }, name="pre_billing"),
                url(r'^pre_billing/mine/(?P<start_date>\d{6})/(?P<end_date>\d{6})/?$', v.pre_billing, {"mine": True, }, name="pre_billing"),
                url(r'lead_blling/(?P<lead_id>\d+)$', v.lead_billing, name="lead_billing"),
                url(r'^datatable/client_bills_in_creation/data/$', t.ClientBillInCreationTableDT.as_view(), name='client_bills_in_creation_DT'),
                url(r'^datatable/client_bills_archive/data/$', t.ClientBillArchiveTableDT.as_view(), name='client_bills_archive_DT'),
                url(r'^datatable/supplier_bills_archive/data/$', t.SupplierBillArchiveTableDT.as_view(), name='supplier_bills_archive_DT'),
                url(r'^graph/billing-jqp$', v.graph_billing_jqp, name="graph_billing_jqp"),
                url(r'^graph/yearly-billing$', v.graph_yearly_billing, name="graph_yearly_billing"),
                url(r'^graph/outstanding-billing$', v.graph_outstanding_billing, name="graph_outstanding_billing"),
                ]
