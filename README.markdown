Pydici is a software for consulting/IT services company to manage:
- commercial leads workflow (from business detection to sales)
- Simple CRM
- workload schedule to forecast people activity
- operation management: timesheet, margin control,
- billing
- optional integration with Nextcloud to manage files

It is written in Python using the Django framework.


# LICENSE

Pydici is available under the GNU Affero Public License v3 or newer (AGPL 3+).
http://www.gnu.org/licenses/agpl-3.0.html

# AUTHOR

Sébastien Renard (Sebastien.Renard@digitalfox.org).


# INSTALLATION
## Production pre requisites:
* python >= 3.9
* mariadb (tested with 10.X)
* memcached
* redis

Pydici can be installed as any Django project. Just drop the code somewhere
and setup your favorite wsgi server (apache/mod_wsgi, gunicorn, uwsgi etc.).

## Development environment

To install all python prerequisites, please do the following: pip install -r requirements.txt. It is strongly advised to use a virtual env.
You will need a running mysql or mariadb with a database named pydici (see pydici/settings.py for default credential)

For development (and only for development), a docker-compose file can be used with mariadb, redis, memcached setup :

    docker-compose up

## Detailed Installation

Drop source code in a directory readable by your wsgi server user 
   git clone https://github.com/digitalfox/pydici.git

Create a virtual env in a directory readable by your apache user and activate it

     virtual-env venv
    . venv/bin/activate

Install prerequisites :

    pip install -r <path to pydici source code>/requirements.txt

Setup your favorite database (mysql/mariaDB or postgresql, mariadb is recommended) and create a schema/base (with UTF-8 character set please) with a valid user that can create/alter/select/delete/update its objects.

Configure your database in pydici/settings.py. Look at django docs to understand the various database options.

Create tables with :

    ./manage.py migrate

Generate a new secret key with ./manage.py generate_secret_key and put it in pydici/settings.py

Collect static files with :

    ./manage.py collectstatic

Setup your apache virtual env:

- activate mod_wsgi.
- activate ssl
- active mod_expires
- add Alias to /media and /static
- define auth backend. 
  - By default, pydici is designed to work with an http front end authentication. Look at https://docs.djangoproject.com/en/dev/howto/auth-remote-user/
  - In debug mode, django userswitch is provided, go to /admin/ and select user in droplist

Periodic tasks are ran by Celery. Scheduling setup is in settins/pydici_celery.py

## Creating initial database

To create the initial database:

        ./manage.py migrate

Or with docker, on development environment : 

      docker exec pydici_django_1 python manage.py migrate


## Notes about scikit learn
Scikit learn is a machine learning framework for python. It is an optional Pydici deps that can predict leads tags and state.
Some comments:

- You need to install scikit-learn, numpy and scipy (pip install -r requirements-sklearn.txt)
- You might need to add the following directive in your apache virual host file to avoid some nasty deadlock during init when using scikit learn : WSGIApplicationGroup %{GLOBAL}
- For proper model caching, you might need to increase memcached object size (1m => 10m) as well as your python client memcache (hardcoded in lib for python-memcached...sic).


## Migrate data from environment
On source:

    ./manage.py dumpdata -o dump.json -e contenttypes -e sessions.Session -e auth.Permission -e admin.LogEntry -e auditlog --natural-foreign

On target:

    # create empty database and play migrations (see above)
    ./manage.py loaddata dump.json
    # or with docker : 
    docker exec pydici_django_1 python manage.py loaddata dump.json 

Note that, loading may fail due to auditlog tracking process done during data loading. In that case, just disable it
temporary by changing the name of the AUDITLOG_INCLUDE_TRACKING_MODELS config key in
in pydici/settings/django.py

# Hosting, support, professional services, custom development
See http://www.enioka.com/pydici-web/
