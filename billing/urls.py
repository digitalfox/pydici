# -*- coding: UTF-8 -*-
"""URL dispatcher for billing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import patterns, url

import billing.views as v


billing_urls = patterns('billing.views',
                        (r'^bill_review', 'bill_review'),
                        (r'^bill_delay', 'bill_payment_delay'),
                        (r'^bill/(?P<bill_id>\d+)/mark_bill_paid$', 'mark_bill_paid'),
                        (r'^file/(?P<nature>.+)/(?P<bill_id>\d+)$', 'bill_file'),
                        url(r'^pdf/(?P<bill_id>\d+)$', v.BillPdf.as_view(), name="bill_pdf"),
                        (r'^html/(?P<bill_id>\d+)$', v.Bill.as_view()),
                        url(r'^bill/client/add$', "client_bill", name='client_bill'),
                        url(r'^bill/client/(?P<bill_id>\d+)$', "client_bill", name='client_bill'),
                        url(r'^pre_billing$', 'pre_billing', {"mine": False, }),
                        url(r'^pre_billing/mine$', 'pre_billing', {"mine": True, }),
                        url(r'^pre_billing/(?P<year>\d+)/(?P<month>\d+)/$', 'pre_billing', {"mine": False, }),
                        url(r'^pre_billing/(?P<year>\d+)/(?P<month>\d+)/mine$', 'pre_billing', {"mine": True, }),
                        (r'^graph/billing-jqp$', 'graph_billing_jqp'),
                        (r'^graph/yearly-billing$', 'graph_yearly_billing'),
                        )
