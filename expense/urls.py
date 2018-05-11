# -*- coding: UTF-8 -*-
"""URL dispatcher for expense module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import patterns, url
from expense.tables import ExpenseTableDT, ExpensePaymentTableDT


expense_urls = patterns('expense.views',
                        (r'^$', 'expenses'),
                        url(r'^(?P<expense_id>\d+)$', 'expenses', name="expense"),
                        (r'^(?P<expense_id>\d+)/receipt$', 'expense_receipt'),
                        (r'^(?P<expense_id>\d+)/(?P<transition_id>\w+)', 'update_expense_state'),
                        url(r'^clone/(?P<clone_from>\d+)$', 'expenses', name="clone_expense"),
                        (r'^mission/(?P<lead_id>\d+)$', 'lead_expenses'),
                        (r'^history/?$', 'expenses_history'),
                        (r'^chargeable/?$', 'chargeable_expenses'),
                        (r'^payment/?$', 'expense_payments'),
                        (r'^payment/(?P<expense_payment_id>\d+)/?$', 'expense_payments'),
                        (r'^payment/(?P<expense_payment_id>\d+)/detail$', 'expense_payment_detail'),
                        url(r'^datatable/all-expense/data/$', ExpenseTableDT.as_view(), name='expense_table_DT'),
                        url(r'^datatable/all-expense-payment/data/$', ExpensePaymentTableDT.as_view(), name='expense_payment_table_DT'),
                        )
