# coding: utf-8

"""
Expense module utils functions
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from time import strftime

def expense_receipt_path(instance, filename):
    """Format full path of expense receipt"""
    return strftime("data/expense/%Y/%m/" + instance.user.username + "/%d-%H%M%S_" + filename)
