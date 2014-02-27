#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Pydici batch module to sync contact from a remote DAV server
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

# Setup batch environnement
from utils import setupBatchEnv
setupBatchEnv()

# Pydici imports
from crm.utils import refreshContact

if __name__ == "__main__":
    refreshContact()
