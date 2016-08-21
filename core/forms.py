# coding:utf-8
"""
Core form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django import forms
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django_select2.forms import ModelSelect2Widget


class SearchForm(forms.Form):
    search = forms.CharField(max_length=100)


class UserChoices(ModelSelect2Widget):
    model = User
    search_fields = ["username__icontains", "first_name__icontains", "last_name__icontains"]

    def get_queryset(self):
        return User.objects.filter(is_active=True)


class PydiciCrispyBaseForm(object):
    """A base form to be subclassed. Factorise common things of all pydici crispy forms"""
    def __init__(self, *args, **kwargs):
        super(PydiciCrispyBaseForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()  # For standard form use
        self.inline_helper = FormHelper()  # For inline (ie embeded in an other form)
        self.inline_helper.form_tag = False
        self.submit = Submit("Submit", _("Save"))
        self.submit.field_classes = "btn btn-default"


class PydiciCrispyModelForm(PydiciCrispyBaseForm, forms.ModelForm):
    """pydici model forms"""
    pass

class PydiciCrispyForm(PydiciCrispyBaseForm, forms.Form):
    """pydici standard (non-model) forms"""
    pass