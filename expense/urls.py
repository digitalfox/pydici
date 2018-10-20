# -*- coding: UTF-8 -*-
"""URL dispatcher for expense module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import url
from expense.tables import ExpenseTableDT, ExpensePaymentTableDT
import expense.views as v


expense_urls = [url(r'^$', v.expenses),
                url(r'^(?P<expense_id>\d+)$', v.expenses, name="expense"),
                url(r'^(?P<expense_id>\d+)/receipt$', v.expense_receipt),
                url(r'^(?P<expense_id>\d+)/delete$', v.expense_delete),
                url(r'^(?P<expense_id>\d+)/(?P<transition_id>\w+)', v.update_expense_state),
                url(r'^clone/(?P<clone_from>\d+)$', v.expenses, name="clone_expense"),
                url(r'^mission/(?P<lead_id>\d+)$', v.lead_expenses),
                url(r'^history/?$', v.expenses_history),
                url(r'^chargeable/?$', v.chargeable_expenses),
                url(r'^payment/?$', v.expense_payments),
                url(r'^payment/(?P<expense_payment_id>\d+)/?$', v.expense_payments),
                url(r'^payment/(?P<expense_payment_id>\d+)/detail$', v.expense_payment_detail),
                url(r'^datatable/all-expense/data/$', ExpenseTableDT.as_view(), name='expense_table_DT'),
                url(r'^datatable/all-expense-payment/data/$', ExpensePaymentTableDT.as_view(), name='expense_payment_table_DT'),
                ]
