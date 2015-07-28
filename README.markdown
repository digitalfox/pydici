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

Setup your favorite database (mysql/mariaDB or postgresql) and create a schema/base (with UTF-8 character set please) with a valid user that can create/alter/select/delete/update its objects.

Configure your database in pydici/settings.py. Look at django docs to understand the various database options.

Create tables with :

    ./manage.py migrate

Generate a new secret key with ./manage.py generate_secret_key and put it in pydici/settings.py

Collect static files with ./manage.py collectstatic

Setup your apache virtual env:
- activate mod_wsgi.
- activate ssl
- active mod_expires
- add Alias to /media and /static
- define auth backend. By default, pydici is designed to work with an http front end authentication. Look at https://docs.djangoproject.com/en/dev/howto/auth-remote-user/

## Updating an existing installation

After pulling the latest changes you need to update the database.

There are three possible situations, depending on whether your installation uses Django Migration. Or still use South or use no miration system at all
Your installation uses South if there is a `south_migrationhistory`

1. Your installation already uses Django Migration. Run these commands:

        ./manage.py migrate
        ./manage.py createsuperuser

2. Your installation uses South:

    Firstly you need to checkout the last pydici version using South "pydici/master", then run these commands:

        ./manage.py syncdb
        ./manage.py migrate

    After that you can update to to a newer version of pydici by running:

        ./manage.py migrate --fake

    Once this is done, future updates will be handled as situation #1.

3. Your installation does not use Django Migration or South yet.

    Firstly you need to checkout the last pydici version using South "pydici/master", then run these commands:

        ./manage.py syncdb
        ./manage.py migrate --all 0001 --fake
        ./manage.py migrate

    After that you can update to to a newer version of pydici by running:

        ./manage.py migrate --fake

    Once this is done, future updates will be handled as situation #1.

## Notes about scikit learn
Scikit learn is a machine learning framework for python. It is an optional Pydici deps that can predict leads tags and state.
Some comments:
- You need to install scikit-learn, numpy and scipy
- You might need to add the following directive in your apache virual host file to avoid some nasty deadlock during init when using scikit learn : WSGIApplicationGroup %{GLOBAL}
- For proper model caching, you might need to increase memcached object size (1m => 10m) as well as your python client memcache (hardcoded in lib for python-memcached...sic).

## Notes about javascript tests
If you want to run javascript tests, you need to install node, phantomjs and casperjs. Node may be included in your distribution. For the two others, here's how to install localy, without any root access:

        npm install phantomjs
        npm install casperjs
