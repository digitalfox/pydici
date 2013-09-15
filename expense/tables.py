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

from expense.models import Expense
from core.templatetags.pydici_filters import link_to_consultant


class ExpenseTable(tables.Table):
    user = tables.Column(verbose_name=_("Consultant"))
    lead = tables.TemplateColumn("""{% if record.lead %}<a href='{% url "leads.views.detail" record.lead.id %}'>{{ record.lead }}</a>{% endif%}""")
    receipt = tables.TemplateColumn("""<a href="{% url 'expense.views.expense_receipt' record.id %}"><img src='{{ MEDIA_URL }}pydici/receipt.png'/></a>""")
    state = tables.Column(sortable=False, verbose_name=_("State"))

    def render_user(self, value):
        return link_to_consultant(value)

    class Meta:
        model = Expense
        sequence = ("user", "description", "lead", "amount", "chargeable", "corporate_card", "receipt", "state", "expense_date", "update_date", "comment")
        fields = sequence
        attrs = {"class": "pydici-tables2"}


class ExpenseWorkflowTable(ExpenseTable):
    user = tables.Column(verbose_name=_("Consultant"))
    lead = tables.TemplateColumn("""{% if record.lead %}<a href='{% url "leads.views.detail" record.lead.id %}'>{{ record.lead }}</a>{% endif%}""")
    receipt = tables.TemplateColumn("""<a href="{% url 'expense.views.expense_receipt' record.id %}"><img src='{{ MEDIA_URL }}pydici/receipt.png'/></a>""")
    state = tables.Column(sortable=False, verbose_name=_("State"))
    transitions = tables.Column(accessor="pk", sortable=False)

    def render_transitions(self, record):
        result = []
        for transition in self.transitions[record.id]:
            result.append("<a href='%s'>%s</a>" % (reverse("expense.views.update_expense_state", args=[record.id, transition.id]), transition))
        if self.expenseEditPerm[record.id]:
            result.append("<a href='%s'>%s</a>" % (reverse("expense.views.expenses", args=[record.id, ]), smart_bytes(_("Edit"))))
        return mark_safe(", ".join(result))

    class Meta:
        model = Expense
        sequence = ("user", "description", "lead", "amount", "chargeable", "corporate_card", "receipt", "state", "transitions", "expense_date", "update_date", "comment")
        fields = sequence
        attrs = {"class": "pydici-tables2"}
