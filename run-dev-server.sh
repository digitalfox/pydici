#!/bin/sh
killall memcached 
/usr/sbin/memcached -l 127.0.0.1 -d -I 32m  -m 128
/usr/sbin/redis-server &
python -Wd manage.py runserver_plus 8888 $*
killall memcached 
killall redis-server
