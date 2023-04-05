#!/usr/bin/env python3
# coding: utf-8

"""
Extract objectives and rates for past years in CSV format
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import csv
from datetime import date
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
from people.models import Consultant


start=date.today()
start=start.replace(year=start.year-1, month=7, day=1)
end=date.today().replace(month=7, day=1)

output = csv.writer(open("objectives.csv", "w"))

output.writerow(["Consultant", "Filiale", "Tx prod N-1", "TJM N-1", "Obj TJM N-1", "Obj prod N-1"])

for c in Consultant.objects.filter(active=True, subcontractor=False, productive=True):
    fc = c.get_financial_conditions(start, end)
    if not fc:
        print(f"Warning, no financial conditions for {c}")
        continue
    line = ([c.trigramme, c.company.name,
            c.get_production_rate(start,end),
            int(sum([i*j for i, j in fc])/sum([j for i, j in fc])),
            c.get_rate_objective(rate_type="DAILY_RATE").rate,
            c.get_rate_objective(rate_type="PROD_RATE").rate/100,
            ])
    output.writerow(line)

