[![Build Status](https://travis-ci.org/digitalfox/pydici.png?branch=master)](https://travis-ci.org/digitalfox/pydici)

Pydici is a software for consulting/IT services company to manage:
- commercial leads workflow (from business detection to sales)
- workload schedule to forecast people activity

It is written in Python using the Django framework.


LICENSE
=======

Pydici is available under the GNU Affero Public License v3 or newer (AGPL 3+).
http://www.gnu.org/licenses/agpl-3.0.html

AUTHOR
======

Sébastien Renard (Sebastien.Renard@digitalfox.org).


INSTALLATION
============

Pydici can be installed as any Django project. Just drop the code somewhere
and setup Apache.

To install all python prerequisites, just do that: pip install -r requirements.txt

Here's a sample Apache/mod_python config file. Pydici code live
is /var/www/pydici and application is published as '/pydici/'.
This prefix (pydici) can be changed in settings.py. Make sure it's
consistent with you Apache/mod_python setup.

--------------8<-------------------------------
LoadModule python_module modules/mod_python.so


<Location "/pydici/">
   SetHandler python-program
    PythonHandler django.core.handlers.modpython
    SetEnv DJANGO_SETTINGS_MODULE pydici.settings
    PythonDebug On
    PythonPath "['/var/www/pydici', '/var/www/'] + sys.path"
</Location>

<Location "/pydici/media/">
    SetHandler None
</Location>

Alias /pydici/media /var/www/pydici/media
--------------8<-------------------------------

Then, please read and update settings.py file according to your configuration. 

Finally, to initialise database, go to pydici directory and run "./manage.py syncdb"