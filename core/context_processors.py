# -*- coding: UTF-8 -*-
"""
Pydici core context processors
@author: Aurélien Gâteau (mail@agateau.com)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from collections import defaultdict
from importlib import import_module

from django.conf import settings


_menu_templates = None


def _init_menu_templates():
    global _menu_templates
    _menu_templates = defaultdict(list)
    for app in settings.INSTALLED_APPS:
        try:
            mod = import_module(app + '.menus')
        except ImportError:
            continue
        for menu_name, template_name in mod.get_menus().items():
            _menu_templates[menu_name].append(template_name)


class MenuWrapper(object):
    def __getitem__(self, name):
        return _menu_templates.get(name)

    def __contains__(self, name):
        return bool(self[name])


def menu(request):
    if _menu_templates is None:
        _init_menu_templates()
    return {
        'pydici_menu': MenuWrapper(),
    }
