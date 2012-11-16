# coding: utf-8
"""
Pydici views decorators
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib.auth.decorators import user_passes_test


def pydici_non_public(function=None):
    """
    Decorator for views that restrict access to "internal" users. For now
    it relies on the staff user flag and is mostly used to allow external people like
    subcontractors to access only to homepage and timesheet page
    """
    actual_decorator = user_passes_test(lambda u: u.is_staff, login_url=None)
    if function:
        return actual_decorator(function)
    return actual_decorator
