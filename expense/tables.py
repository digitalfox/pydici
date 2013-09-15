# coding: utf-8
"""
Pydici leads tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import ugettext as _

import django_tables2 as tables
from django_tables2.utils import A

from expense.models import Expense
from core.templatetags.pydici_filters import link_to_consultant


class ExpenseTable(tables.Table):
    user = tables.Column(verbose_name=_("Consultant"))
    receipt = tables.TemplateColumn("""<a href="{% url 'expense.views.expense_receipt' record.id %}"><img src='{{ MEDIA_URL }}pydici/receipt.png'/></a>""")

    def render_user(self, value):
        return link_to_consultant(value)

    class Meta:
        model = Expense
        sequence = ("user", "description", "lead", "amount", "chargeable", "receipt", "state", "expense_date", "update_date", "comment")
        fields = sequence
