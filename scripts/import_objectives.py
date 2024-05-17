#!/usr/bin/env python3
# coding: utf-8

"""
Import objectives and rates from CSV format
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import csv
from datetime import datetime
import sys
import os
from os.path import abspath, join, pardir, dirname


# # Setup django envt & django imports
PYDICI_DIR = abspath(join(dirname(__file__), pardir))
os.environ['DJANGO_SETTINGS_MODULE'] = "pydici.settings"

sys.path.append(PYDICI_DIR)  # Add project path to python path

# Ensure we are in the good current working directory (pydici home)
os.chdir(PYDICI_DIR)

# Init and model loading
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

# Pydici imports
from people.models import Consultant, RateObjective

objectives = csv.reader(open(sys.argv[1], "r"))

for line in objectives:
    if not line[0] or line[0]=="Consultant":
        continue
    try:
        c = Consultant.objects.get(trigramme=line[0])
    except:
        print(f"Warning, no consultant for {line[0]}")
        continue
    start = datetime.strptime(line[21], "%Y-%m-%d")
    prod_rate = float(line[10].strip("%"))
    daily_rate = int(line[7])
    RateObjective.objects.get_or_create(consultant=c, start_date=start, rate=daily_rate, rate_type="DAILY_RATE")
    RateObjective.objects.get_or_create(consultant=c, start_date=start, rate=prod_rate, rate_type="PROD_RATE")

