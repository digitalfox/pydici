# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_fix_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='groupfeature',
            name='feature',
            field=models.CharField(max_length=80, verbose_name='Feature', choices=[('3rdparties', "3rd Parties: Access to the 'Third parties' menu"), ('contacts_write', 'Contacts, write access: Allow adding, editing, removing contacts'), ('leads', "Leads: Access to the 'Leads' menu"), ('leads_list_all', "Leads, list all: Access to the 'Leads > All leads' menu entry"), ('leads_profitability', "Leads, profitability: Access to the 'Profitability' information in lead description"), ('management', "Management: Access to the 'Management' menu"), ('menubar', 'Menubar: Show the menubar'), ('reports', "Reports: Access to the 'Reports' menu"), ('search', 'Search: Allow searching'), ('staffing', 'Staffing: Access to staffing features'), ('staffing_mass', 'Staffing, mass edit: Access to mass staffing features'), ('timesheet_all', 'Timesheet, all: Access to all timesheets of all users'), ('timesheet_current_month', 'Timesheet, current month: Access to current month timesheets of all users'), ('billing_management', 'Manage bills, allow to mark bills sent, paid etc.'), ('billing_request', 'Create bills and proposed them to billing team ')]),
        ),
    ]
