# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in People models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import gettext as _

from people.models import Consultant
from core.utils import user_has_feature


def get_team_scopes(subsidiary, team, only_productive=True):
    """Define scopes than can be used to filter data on team".
    @:param team
    @:return: scopes, scope_current_filter, scope_current_url_filter"""

    # Gather scopes
    scopes = [(None, "all", _("Everybody")), ]

    consultants = Consultant.objects.filter(active=True, subcontractor=False)
    if only_productive:
        consultants = consultants.filter(productive=True)
    if subsidiary:
        consultants = consultants.filter(company=subsidiary)
    consultants = consultants.values_list("staffing_manager", "staffing_manager__name").order_by().distinct()
    for manager_id, manager_name in consultants:
        scopes.append(
            ("team_id", "team_id=%s" % manager_id, _("team %(manager_name)s") % {"manager_name": manager_name}))

    # Compute uri and filters
    if team:
        scope_current_filter = "team_id=%s" % team.id
        scope_current_url_filter = "team/%s" % team.id
    else:
        scope_current_filter = ""
        scope_current_url_filter = ""

    return scopes, scope_current_filter, scope_current_url_filter


def users_are_in_same_company(user1, user2):
    """Returns true if user1 and user2 according Consultant belongs to the same company"""
    return (Consultant.objects.get(trigramme=user1.username.upper()).company ==
            Consultant.objects.get(trigramme=user2.username.upper()).company)


def subcontractor_is_user(consultant, user):
    """Ensure given subcontractor consultant is really the user. Used to limit consultant page to self for subcontractors"""
    if not user_has_feature(user, "internal_access"):
        if consultant.trigramme.lower() != user.username.lower():
            return False
    return True
