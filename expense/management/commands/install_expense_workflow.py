from django.core.management.base import BaseCommand, CommandError

from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group

from workflows.models import WorkflowModelRelation, WorkflowPermissionRelation, StatePermissionRelation, \
                             Workflow, State, Transition
from permissions.models import Permission, Role, PrincipalRoleRelation


class Command(BaseCommand):
    help = 'Install default workflow'

    def handle(self, *args, **options):
        permission_expense_management = Permission.objects.create(name=u'expense management', codename=u'expense_management')
        permission_expense_control = Permission.objects.create(name=u'expense control', codename=u'expense_control')
        permission_expense_edit = Permission.objects.create(name=u'expense edit', codename=u'expense_edit')

        # Roles
        role_manager = Role.objects.create(name=u'expense manager')
        role_owner = Role.objects.create(name=u'expense owner')
        role_paymaster = Role.objects.create(name=u'expense paymaster')

        # Roles <=> group relationship
        PrincipalRoleRelation.objects.create(role=role_owner,
                                             group=Group.objects.get(name="expense_requester"))
        PrincipalRoleRelation.objects.create(role=role_manager,
                                             group=Group.objects.get(name="expense_manager"))
        PrincipalRoleRelation.objects.create(role=role_paymaster,
                                             group=Group.objects.get(name="expense_paymaster"))

        # Create the expense the workflow
        expense_workflow = Workflow.objects.create(name=u"expense")

        # Set default workflow for "expense" objects
        WorkflowModelRelation.objects.create(content_type=ContentType.objects.get(app_label="expense", model="expense"),
                                             workflow=expense_workflow)

        # Associates permissions to workflow
        for permission in (permission_expense_management, permission_expense_control, permission_expense_edit):
            WorkflowPermissionRelation.objects.create(workflow=expense_workflow,
                                                      permission=permission)

        # States
        state_requested = State.objects.create(name=u'requested', workflow=expense_workflow)
        state_validated = State.objects.create(name=u'validated', workflow=expense_workflow)
        state_rejected = State.objects.create(name=u'rejected', workflow=expense_workflow)
        state_needs_information = State.objects.create(name=u'needs information', workflow=expense_workflow)
        state_paid = State.objects.create(name=u'paid', workflow=expense_workflow)

        # Start by requested state
        expense_workflow.initial_state = state_requested
        expense_workflow.save()

        # At each state, we create permissions
        StatePermissionRelation.objects.create(state=state_requested,
                                               permission=permission_expense_edit,
                                               role=role_owner)

        StatePermissionRelation.objects.create(state=state_requested,
                                               permission=permission_expense_management,
                                               role=role_manager)

        StatePermissionRelation.objects.create(state=state_needs_information,
                                               permission=permission_expense_edit,
                                               role=role_owner)

        StatePermissionRelation.objects.create(state=state_validated,
                                               permission=permission_expense_control,
                                               role=role_paymaster)

        # Workflow transitions between states
        transition_validate = Transition.objects.create(name=u'validate',
                                                           workflow=expense_workflow,
                                                           destination=state_validated,
                                                           condition=u'',
                                                           permission=permission_expense_management)

        transition_ask_information = Transition.objects.create(name=u'ask information',
                                                           workflow=expense_workflow,
                                                           destination=state_needs_information,
                                                           condition=u'',
                                                           permission=permission_expense_control)

        transition_reject = Transition.objects.create(name=u'reject',
                                                           workflow=expense_workflow,
                                                           destination=state_rejected,
                                                           condition=u'',
                                                           permission=permission_expense_management)

        transition_control = Transition.objects.create(name=u'control',
                                                           workflow=expense_workflow,
                                                           destination=state_paid,
                                                           condition=u'',
                                                           permission=permission_expense_control)

        # Add transition allowed from each state
        state_requested.transitions.add(transition_validate)
        state_requested.transitions.add(transition_ask_information)
        state_requested.transitions.add(transition_reject)

        state_validated.transitions.add(transition_ask_information)
        state_validated.transitions.add(transition_control)

        state_needs_information.transitions.add(transition_validate)
        state_needs_information.transitions.add(transition_reject)
