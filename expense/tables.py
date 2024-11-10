# coding: utf-8
"""
Pydici leads tables
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import gettext as _
from django.db.models import Q
from django.utils.safestring import mark_safe
from django.template import Template, RequestContext
from django.template.loader import get_template
from django_datatables_view.base_datatable_view import BaseDatatableView

import django_tables2 as tables
from django_tables2.utils import A

from expense.models import Expense, ExpensePayment
from people.models import Consultant
from core.templatetags.pydici_filters import link_to_consultant
from core.utils import TABLES2_HIDE_COL_MD, to_int_or_round
from core.decorator import PydiciFeatureMixin, PydiciNonPublicdMixin, PydiciSubcontractordMixin
from expense.utils import expense_transition_to_state_display, user_expense_perm, can_edit_expense, expense_next_states


class ExpenseTableDT(PydiciSubcontractordMixin, PydiciFeatureMixin, BaseDatatableView):
    """Expense table backend for datatable"""
    pydici_feature = {"expense"}
    columns = ["pk", "user", "category", "description", "lead", "amount", "vat", "receipt", "chargeable",
               "corporate_card", "state", "creation_date", "expense_date", "update_date", "comment"]
    order_columns = columns
    max_display_length = 500
    date_template = get_template("core/_date_column.html")
    receipt_template = get_template("expense/_receipt_column.html")
    state_template = get_template("expense/_expense_state_column.html")
    ko_sign = mark_safe("""<i class="bi bi-x" style="color:red"><span class="visuallyhidden">No</span></i>""")
    ok_sign = mark_safe("""<i class="bi bi-check" style="color:green"><span class="visuallyhidden">Yes</span></i>""")
    vat_template = get_template("expense/_expense_vat_column.html")

    def get_initial_queryset(self):
        expense_administrator, expense_subsidiary_manager, expense_manager, expense_paymaster, expense_requester = user_expense_perm(self.request.user)
        consultant = Consultant.objects.get(trigramme__iexact=self.request.user.username)

        self.can_edit_vat = expense_administrator or expense_paymaster  # Used for vat column render

        if expense_subsidiary_manager:
            user_team = consultant.user_team(subsidiary=True)
        elif expense_manager:
            user_team = consultant.user_team()
        else:
            user_team = []

        expenses = Expense.objects.all()
        if not expense_paymaster:
            expenses = expenses.filter(Q(user=self.request.user) | Q(user__in=user_team))
        return expenses.select_related("lead__client__contact", "lead__client__organisation__company", "user")

    def get_filters(self, search):
        """Custom method to get Q filter objects that should be combined with OR keyword"""
        filters = []
        try:
            # Just try to cast to see if we have a number but use str for filter to allow proper casting by django himself
            float(search)
            filters = [Q(amount=search), Q(vat=search), Q(id=int(float(search)))]

        except ValueError:
            # search term is not a number
            filters.extend([Q(comment__icontains=search),
                            Q(description__icontains=search),
                            Q(user__first_name__icontains=search),
                            Q(user__last_name__icontains=search),
                            Q(user__username=search),
                            Q(lead__client__organisation__company__name__icontains=search),
                            Q(lead__client__organisation__name__iexact=search),
                            Q(lead__description__icontains=search),
                            Q(lead__deal_id__icontains=search)])
        return filters

    def filter_queryset(self, qs):
        """ simple search on some attributes"""
        search = self.request.GET.get('search[value]', None)
        if search:
            filters = self.get_filters(search)
            query = Q()
            for f in filters:
                query |= f
            qs = qs.filter(query).distinct()
        return qs

    def render_column(self, row, column):
        if column == "user":
            return link_to_consultant(row.user)
        elif column == "receipt":
            return self.receipt_template.render(context={"record": row}, request=self.request)
        elif column == "lead":
            if row.lead:
                return "<a href='{0}'>{1}</a>".format(row.lead.get_absolute_url(), row.lead)
            else:
                return "-"
        elif column in ("creation_date", "expense_date"):
            return self.date_template.render(context={"date": getattr(row, column)}, request=self.request)
        elif column == "update_date":
            return row.update_date.strftime("%x %X")
        elif column in ("chargeable", "corporate_card"):
            if getattr(row, column):
                return self.ok_sign
            else:
                return self.ko_sign
        elif column == "state":
            return self.state_template.render(context={"record": row}, request=self.request)
        elif column == "amount":
            return to_int_or_round(row.amount, 2)
        elif column == "vat":
            return self.vat_template.render(context={"expense": row, "can_edit_vat": self.can_edit_vat}, request=self.request)
        else:
            return super(ExpenseTableDT, self).render_column(row, column)


class ExpenseTable(tables.Table):
    id = tables.TemplateColumn("""<a href="{{ record.get_absolute_url }}">{{ record.id }}</a>""", verbose_name="#")
    description = tables.Column(attrs={"td": {"class": "description"}})
    amount = tables.Column(attrs={"td": {"class": "amount"}})
    user = tables.Column(verbose_name=_("Consultant"))
    lead = tables.TemplateColumn("""{% if record.lead %}<a href='{% url "leads:detail" record.lead.id %}'>{{ record.lead }}</a>{% endif%}""")
    receipt = tables.TemplateColumn(template_name="expense/_receipt_column.html")
    state = tables.TemplateColumn(template_name="expense/_expense_state_column.html", orderable=False)
    expense_date = tables.TemplateColumn("""<span title="{{ record.expense_date|date:"Ymd" }}">{{ record.expense_date }}</span>""")  # Title attr is just used to have an easy to parse hidden value for sorting
    update_date = tables.TemplateColumn("""<span title="{{ record.update_date|date:"Ymd" }}">{{ record.update_date }}</span>""", attrs=TABLES2_HIDE_COL_MD)  # Title attr is just used to have an easy to parse hidden value for sorting
    transitions_template = get_template("expense/_expense_transitions_column.html")
    vat_template = get_template("expense/_expense_vat_column.html")

    def render_user(self, value):
        return link_to_consultant(value)

    def render_vat(self, record):
        return self.vat_template.render(context={"expense": record, "can_edit_vat": True})

    class Meta:
        model = Expense
        sequence = ("id", "user", "description", "lead", "amount", "vat", "chargeable", "corporate_card", "receipt", "state", "expense_date", "update_date", "comment")
        fields = sequence
        attrs = {"class": "pydici-tables2 table table-hover table-striped table-sm", "id": "expense_table"}
        orderable = False
        order_by = "-expense_date"


class ExpenseWorkflowTable(ExpenseTable):
    transitions = tables.Column(accessor="pk")

    class Meta:
        sequence = ("id", "user", "description", "lead", "amount", "chargeable", "corporate_card", "receipt", "state", "transitions", "expense_date", "update_date", "comment")
        fields = sequence


class UserExpenseWorkflowTable(ExpenseWorkflowTable):
    def render_transitions(self, record):
        return self.transitions_template.render(context={"record": record,
                                                         "transitions": [],
                                                         "expense_edit_perm": can_edit_expense(record, self.request.user)},
                                                request=self.request)

    class Meta:
        attrs = {"class": "pydici-tables2 table table-hover table-striped table-sm", "id": "user_expense_workflow_table"}
        prefix = "user_expense_workflow_table"
        orderable = False


class ManagedExpenseWorkflowTable(ExpenseWorkflowTable):
    description = tables.TemplateColumn("""{% load l10n %} <span id="managed_expense_{{record.id|unlocalize }}">{{ record.description }}</span>""",
                                        attrs={"td": {"class": "description"}})

    def render_transitions(self, record):
        transitions = [(t, expense_transition_to_state_display(t), expense_transition_to_state_display(t)[0:2]) for t in expense_next_states(record, self.request.user)]
        return self.transitions_template.render(context={"record": record,
                                                         "transitions": transitions,
                                                         "expense_edit_perm": can_edit_expense(record, self.request.user)},
                                                request=self.request)

    class Meta:
        attrs = {"class": "pydici-tables2 table table-hover table-striped table-sm", "id": "managed_expense_workflow_table"}
        prefix = "managed_expense_workflow_table"
        orderable = False


class ExpensePaymentTable(tables.Table):
    user = tables.Column(verbose_name=_("Consultant"), orderable=False)
    amount = tables.Column(verbose_name=_("Amount"), orderable=False)
    id = tables.LinkColumn(viewname="expense:expense_payment_detail", args=[A("pk")])
    detail = tables.TemplateColumn("""<a href="{% url 'expense:expense_payment_detail' record.id %}"><img src='{{MEDIA_URL}}pydici/menu/magnifier.png'/></a>""", verbose_name=_("detail"), orderable=False)
    modify = tables.TemplateColumn("""<a href="{% url 'expense:expense_payments' record.id %}"><img src='{{MEDIA_URL}}img/icon_changelink.gif'/></a>""", verbose_name=_("change"), orderable=False)
    payment_date = tables.TemplateColumn("""<span title="{{ record.payment_date|date:"Ymd" }}">{{ record.payment_date }}</span>""")  # Title attr is just used to have an easy to parse hidden value for sorting

    def render_user(self, value):
        return link_to_consultant(value)

    class Meta:
        model = ExpensePayment
        sequence = ("id", "user", "amount", "payment_date")
        fields = sequence
        attrs = {"class": "pydici-tables2 table table-hover table-striped table-sm", "id": "expense_payment_table"}
        order_by = "-id"
        orderable = False


class ExpensePaymentTableDT(PydiciNonPublicdMixin, PydiciFeatureMixin, BaseDatatableView):
    """Expense payment table backend for datatable"""
    pydici_feature = {"reports"}
    columns = ["pk", "user",  "amount", "payment_date", "modification"]
    order_columns = columns
    max_display_length = 500
    date_template = get_template("core/_date_column.html")
    modification_template = Template("""<a href="{% url 'expense:expense_payments' record.id %}"><img src='{{MEDIA_URL}}img/icon_changelink.gif'/>""")

    def get_initial_queryset(self):
        try:
            consultant = Consultant.objects.get(trigramme__iexact=self.request.user.username)
            user_team = consultant.user_team()
        except Consultant.DoesNotExist:
            user_team = []

        expensePayments = ExpensePayment.objects.all()
        expense_administrator, expense_subsidiary_manager, expense_manager, expense_paymaster, expense_requester = user_expense_perm(self.request.user)
        if not expense_paymaster:
            expensePayments = expensePayments.filter(
                Q(expense__user=self.request.user) | Q(expense__user__in=user_team)).distinct()
        return expensePayments

    def filter_queryset(self, qs):
        """ simple search on some attributes"""
        search = self.request.GET.get('search[value]', None)
        if search:
            qs = qs.filter(Q(expense__comment__icontains=search) |
                           Q(expense__description__icontains=search) |
                           Q(expense__user__first_name__icontains=search) |
                           Q(expense__user__last_name__icontains=search) |
                           Q(expense__user__username=search) |
                           Q(expense__lead__client__organisation__company__name__icontains=search) |
                           Q(expense__lead__client__organisation__name__iexact=search) |
                           Q(expense__lead__description__icontains=search) |
                           Q(expense__lead__deal_id__icontains=search))
            qs = qs.distinct()
        return qs

    def render_column(self, row, column):
        if column == "user":
            return link_to_consultant(row.user())
        elif column == "payment_date":
            return self.date_template.render(context={"date": row.payment_date}, request=self.request)
        elif column == "amount":
            return to_int_or_round(row.amount(), 2)
        elif column == "modification":
            return self.modification_template.render(RequestContext(self.request, {"record": row}))
        else:
            return super(ExpensePaymentTableDT, self).render_column(row, column)
