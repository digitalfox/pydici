# coding:utf-8
"""
Core form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django import forms


class SearchForm(forms.Form):
    search = forms.CharField(max_length=100)


class PydiciSelect2Field():
    def security_check(self, request, *args, **kwargs):
        """
        Returns ``False`` if security check fails.

        :param request: The Ajax request object.
        :type request: :py:class:`django.http.HttpRequest`

        :param args: The ``*args`` passed to :py:meth:`django.views.generic.base.View.dispatch`.
        :param kwargs: The ``**kwargs`` passed to :py:meth:`django.views.generic.base.View.dispatch`.

        :return: A boolean value, signalling if check passed or failed.
        :rtype: :py:obj:`bool`

        """
        return request.user.is_authenticated() and request.user.is_active