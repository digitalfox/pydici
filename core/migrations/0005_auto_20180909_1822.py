# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_fix_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='groupfeature',
            name='feature',
            field=models.CharField(max_length=80, verbose_name='Feature', choices=[(b'3rdparties', "3rd Parties: Access to the 'Third parties' menu"), (b'contacts_write', 'Contacts, write access: Allow adding, editing, removing contacts'), (b'leads', "Leads: Access to the 'Leads' menu"), (b'leads_list_all', "Leads, list all: Access to the 'Leads > All leads' menu entry"), (b'leads_profitability', "Leads, profitability: Access to the 'Profitability' information in lead description"), (b'management', "Management: Access to the 'Management' menu"), (b'menubar', 'Menubar: Show the menubar'), (b'reports', "Reports: Access to the 'Reports' menu"), (b'search', 'Search: Allow searching'), (b'staffing', 'Staffing: Access to staffing features'), (b'staffing_mass', 'Staffing, mass edit: Access to mass staffing features'), (b'timesheet_all', 'Timesheet, all: Access to all timesheets of all users'), (b'timesheet_current_month', 'Timesheet, current month: Access to current month timesheets of all users'), (b'billing_management', 'Manage bills, allow to mark bills sent, paid etc.'), (b'billing_request', 'Create bills and proposed them to billing team ')]),
        ),
    ]
