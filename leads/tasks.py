# coding: utf-8

"""
Module that handle asynchronous tasks
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from celery import shared_task
from leads.learn import compute_leads_state, compute_leads_tags, compute_lead_similarity
from leads.utils import merge_lead_tag, remove_lead_tag, tag_leads_files


@shared_task
def learning_warmup():
    """Warmup cache while people are sleeping to avoid punishing the first user of the day"""
    compute_leads_state.delay(relearn=True)
    compute_leads_tags.delay(relearn=True)
    compute_lead_similarity.delay(relearn=True)
