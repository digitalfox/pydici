# coding: utf-8

"""
Module that handle asynchronous tasks
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from leads.learn import compute_leads_state, compute_leads_tags, compute_lead_similarity
from leads.utils import merge_lead_tag, remove_lead_tag, tag_leads_files
