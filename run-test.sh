#!/bin/sh

cd $(dirname $0)

PATH=node_modules/.bin/:$PATH OPENSSL_CONF=/etc/ssl python manage.py test
