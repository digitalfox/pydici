#!/bin/sh
# Extract messages from source code, update .po file and compile .mo file
# Sebastien Renard (Sebastien.Renard@digitalfox.org) - april 2010

OLD=$PWD
cd $(dirname $0)
python manage.py makemessages -a -e ".html,.txt,.py" -i data -i venv -i venv3 -i node_modules
cd locale && python ../manage.py compilemessages
cd $OLD
