# coding: utf-8

"""
Celery initialisation
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import os

from django.core.mail import mail_admins
from celery import Celery
from celery.signals import task_failure

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pydici.settings")

app = Celery("pydici")
app.config_from_object("django.conf:settings", namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@task_failure.connect()
def email_on_task_crash(**kwargs):
    """Simple mail alert on task crash"""
    subject = "Pydici task error in {sender.name}".format(**kwargs).replace("\n", " ")
    message = "{sender.name} was called with {args} / {kwargs} and failed with error message:\n\n{einfo}".format(**kwargs)
    mail_admins(subject, message)
