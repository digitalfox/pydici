#!/bin/sh

cd $(dirname $0)

if [ -z "$RUNNING_IN_GH"  ];
then
	echo "running test in local"
else
	echo "inside tests in GH"
	sleep 10
fi

PATH=node_modules/.bin/:$PATH OPENSSL_CONF=/etc/ssl python manage.py test $*
