# coding: utf-8

"""
Module that handle asynchronous tasks
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.core import management
from celery import shared_task

@shared_task
def sessions_cleanup():
    """Cleanup django sessions"""
    management.call_command("clearsessions", verbosity=0)