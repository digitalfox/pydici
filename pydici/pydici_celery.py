# coding: utf-8

"""
Celery initialisation
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import os

from celery import Celery, signature
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pydici.settings")

app = Celery("pydici")
app.config_from_object("django.conf:settings", namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


# Define periodic tasks
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Warn users about incomplete timesheet
    #TODO: get scheduling from parameters
    sender.add_periodic_task(crontab(hour=6, minute=0, day_of_month="1"),
                             signature("staffing.tasks.warn_for_incomplete_timesheet",
                                       kargs={"warn_overbooking": True, "days": None, "month": "last"}),
                             name="Warn users for incomplete timesheet")
    sender.add_periodic_task(crontab(hour=6, minute=0, day_of_week="0-5"),
                             signature("staffing.tasks.warn_for_incomplete_timesheet",
                                       kargs={"warn_overbooking": False, "days": None, "month": "last"}),
                             name="Warn users for incomplete timesheet")
    sender.add_periodic_task(crontab(hour=6, minute=0, day_of_month="21-31"),
                             signature("staffing.tasks.warn_for_incomplete_timesheet",
                                       kargs={"warn_overbooking": False, "days": 20, "month": "current"}),
                             name="Warn users for incomplete timesheet")
