# -*- coding: UTF-8 -*-
"""URL dispatcher for expense module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.urls import re_path
from expense.tables import ExpenseTableDT, ExpensePaymentTableDT
import expense.views as v


expense_urls = [ re_path(r'^$', v.expenses, name="expenses"),
                 re_path(r'^(?P<expense_id>\d+)$', v.expense, name="expense"),
                 re_path(r'^(?P<expense_id>\d+)/receipt$', v.expense_receipt, name="expense_receipt"),
                 re_path(r'^(?P<expense_id>\d+)/delete$', v.expense_delete, name="expense_delete"),
                 re_path(r'^(?P<expense_id>\d+)/change$', v.expenses, name="expenses"),
                 re_path(r'^(?P<expense_id>\d+)/expense_vat$', v.update_expense_vat, name="update_expense_vat"),
                 re_path(r'^(?P<expense_id>\d+)/(?P<target_state>\w+)$', v.update_expense_state, name="update_expense_state"),
                 re_path(r'^clone/(?P<clone_from>\d+)$', v.expenses, name="clone_expense"),
                 re_path(r'^mission/(?P<lead_id>\d+)$', v.lead_expenses, name="lead_expenses"),
                 re_path(r'^history/?$', v.expenses_history, name="expenses_history"),
                 re_path(r'^chargeable/?$', v.chargeable_expenses, name="chargeable_expenses"),
                 re_path(r'^payment/?$', v.expense_payments, name="expense_payments"),
                 re_path(r'^payment/(?P<expense_payment_id>\d+)/?$', v.expense_payments, name="expense_payments"),
                 re_path(r'^payment/(?P<expense_payment_id>\d+)/detail$', v.expense_payment_detail, name="expense_payment_detail"),
                 re_path(r'^datatable/all-expense/data/$', ExpenseTableDT.as_view(), name='expense_table_DT'),
                 re_path(r'^datatable/all-expense-payment/data/$', ExpensePaymentTableDT.as_view(), name='expense_payment_table_DT'),
                ]
