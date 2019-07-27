#!/bin/sh
killall memcached 
/usr/sbin/memcached -l 127.0.0.1 -d 
python -Wd manage.py runserver_plus 8888 $*
killall memcached 
