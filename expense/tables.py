# coding: utf-8
"""
Pydici leads tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.encoding import smart_bytes

import django_tables2 as tables
from django_tables2.utils import A

from expense.models import Expense, ExpensePayment
from core.templatetags.pydici_filters import link_to_consultant
from core.utils import TABLES2_HIDE_COL_MD


class ExpenseTable(tables.Table):
    user = tables.Column(verbose_name=_("Consultant"))
    lead = tables.TemplateColumn("""{% if record.lead %}<a href='{% url "leads.views.detail" record.lead.id %}'>{{ record.lead }}</a>{% endif%}""")
    receipt = tables.TemplateColumn("""{% if record.receipt %}<a href="{% url 'expense.views.expense_receipt' record.id %}" data-remote="false" data-toggle="modal" data-target="#expenseModal"><img src='{{ MEDIA_URL }}pydici/receipt.png'/></a>{% endif %}""")
    state = tables.TemplateColumn("""{% load i18n %}{% if record.expensePayment %}
                                                        <a href="{% url 'expense.views.expense_payment_detail' record.expensePayment.id %}">{% trans "Paid" %}</a>
                                                    {% else %}{{ record.state }}{% endif %}""", verbose_name=_("State"), orderable=False)
    expense_date = tables.TemplateColumn("""<span title="{{ record.expense_date|date:"Ymd" }}">{{ record.expense_date }}</span>""")  # Title attr is just used to have an easy to parse hidden value for sorting
    update_date = tables.TemplateColumn("""<span title="{{ record.update_date|date:"Ymd" }}">{{ record.update_date }}</span>""", attrs=TABLES2_HIDE_COL_MD)  # Title attr is just used to have an easy to parse hidden value for sorting


    def render_user(self, value):
        return link_to_consultant(value)

    class Meta:
        model = Expense
        sequence = ("user", "description", "lead", "amount", "chargeable", "corporate_card", "receipt", "state", "expense_date", "update_date", "comment")
        fields = sequence
        attrs = {"class": "pydici-tables2 table table-hover table-striped table-condensed", "id": "expense_table"}
        orderable = False
        order_by = "-expense_date"


class ExpenseWorkflowTable(ExpenseTable):
    transitions = tables.Column(accessor="pk")

    def render_transitions(self, record):
        result = []
        for transition in self.transitionsData[record.id]:
            result.append("""<a href="javascript:;" onClick="$.get('%s', process_expense_transition)">%s</a>"""
                          % (reverse("expense.views.update_expense_state", args=[record.id, transition.id]), transition))
        if self.expenseEditPerm[record.id]:
            result.append("<a href='%s'>%s</a>" % (reverse("expense.views.expenses", args=[record.id, ]), smart_bytes(_("Edit"))))
        return mark_safe(", ".join(result))

    class Meta:
        sequence = ("user", "description", "lead", "amount", "chargeable", "corporate_card", "receipt", "state", "transitions", "expense_date", "update_date", "comment")
        fields = sequence


class UserExpenseWorkflowTable(ExpenseWorkflowTable):
    class Meta:
        attrs = {"class": "pydici-tables2 table table-hover table-striped table-condensed", "id": "user_expense_workflow_table"}
        prefix = "user_expense_workflow_table"
        orderable = False


class ManagedExpenseWorkflowTable(ExpenseWorkflowTable):
    description = tables.TemplateColumn("""{% load l10n %} <span id="managed_expense_{{record.id|unlocalize }}">{{ record.description }}</span>""")
    class Meta:
        attrs = {"class": "pydici-tables2 table table-hover table-striped table-condensed", "id": "managed_expense_workflow_table"}
        prefix = "managed_expense_workflow_table"
        orderable = False


class ExpensePaymentTable(tables.Table):
    user = tables.Column(verbose_name=_("Consultant"), orderable=False)
    amount = tables.Column(verbose_name=_("Amount"), orderable=False)
    id = tables.LinkColumn(viewname="expense.views.expense_payment_detail", args=[A("pk")])
    detail = tables.TemplateColumn("""<a href="{% url 'expense.views.expense_payment_detail' record.id %}"><img src='{{MEDIA_URL}}pydici/menu/magnifier.png'/></a>""", verbose_name=_("detail"), orderable=False)
    modify = tables.TemplateColumn("""<a href="{% url 'expense.views.expense_payments' record.id %}"><img src='{{MEDIA_URL}}img/icon_changelink.gif'/></a>""", verbose_name=_("change"), orderable=False)
    payment_date = tables.TemplateColumn("""<span title="{{ record.payment_date|date:"Ymd" }}">{{ record.payment_date }}</span>""")  # Title attr is just used to have an easy to parse hidden value for sorting

    def render_user(self, value):
        return link_to_consultant(value)

    class Meta:
        model = ExpensePayment
        sequence = ("id", "user", "amount", "payment_date")
        fields = sequence
        attrs = {"class": "pydici-tables2 table table-hover table-striped table-condensed", "id": "expense_payment_table"}
        order_by = "-id"
        orderable = False
