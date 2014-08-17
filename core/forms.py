# coding:utf-8
"""
Core form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django import forms
from django.core.validators import EMPTY_VALUES
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django_select2.fields import AutoModelSelect2Field


class SearchForm(forms.Form):
    search = forms.CharField(max_length=100)


class PydiciSelect2Field():
    empty_values = EMPTY_VALUES

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


class UserChoices(PydiciSelect2Field, AutoModelSelect2Field):
    queryset = User.objects.filter(is_active=True)
    search_fields = ["username__icontains", "first_name__icontains", "last_name__icontains"]


class PydiciCrispyModelForm(forms.ModelForm):
    """A base form to be subclassed. Factorise common things of all pydici crispy forms"""
    def __init__(self, *args, **kwargs):
        super(PydiciCrispyModelForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.submit = Submit("Submit", _("Save"))
        self.submit.field_classes = "btn btn-default"
