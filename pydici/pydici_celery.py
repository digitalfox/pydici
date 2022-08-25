# coding: utf-8

"""
Celery initialisation
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import os

from celery import Celery, signature

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pydici.settings")

app = Celery("pydici")
app.config_from_object("django.conf:settings", namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()
