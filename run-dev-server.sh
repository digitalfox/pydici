#!/bin/sh
./manage.py runserver --adminmedia=$(dirname $0)/media/ $* 8888
