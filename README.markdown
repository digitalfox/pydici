[![Build Status](https://travis-ci.org/digitalfox/pydici.png?branch=master)](https://travis-ci.org/digitalfox/pydici)

Pydici is a software for consulting/IT services company to manage:
- commercial leads workflow (from business detection to sales)
- workload schedule to forecast people activity

It is written in Python using the Django framework.


# LICENSE

Pydici is available under the GNU Affero Public License v3 or newer (AGPL 3+).
http://www.gnu.org/licenses/agpl-3.0.html

# AUTHOR

Sébastien Renard (Sebastien.Renard@digitalfox.org).


# INSTALLATION

Pydici can be installed as any Django project. Just drop the code somewhere
and setup Apache.

To install all python prerequisites, just do that: pip install -r requirements.txt. It is strongly advised to use a virtual env.

## Detailed installation

Drop source code in a directory readable by your apache user
   git clone https://github.com/digitalfox/pydici.git

Create a virtual env in a directory readable by your apache user and activate it
   virtual-env pydici-venv
   . pydici-venv/bin/activate

Install prerequisites :
   pip install -r <path to pydici source code>/requirements.txt

Setup your favorite database (mysql/mariaDB or postgresql) and create a schema/base (with UTF-8 character set please) with a valid user that can create/alterselect/delete/update its objects.

Configure your database in pydici/settings.py. Look at django docs to understand the various database options.

Create tables with :
   ./manage.py syncdb

Generate a new secret key with ./manage.py generate_secret_key and put it in pydici/settings.py

Collect static files with ./manage.py collectstatic

Setup your apache virtual env:
- activate mod_wsgi.
- activate ssl
- active mod_expires
- add Alias to /media and /static
- define auth backend. By default, pydici is designed to work with an http front end authentication. Look at https://docs.djangoproject.com/en/dev/howto/auth-remote-user/
