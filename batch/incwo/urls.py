from django.conf.urls import patterns


incwo_urls = patterns('batch.incwo.views',
                      (r'^/?$', 'imports'),
                      (r'^/(?P<log_dir>[-:T0-9]+)$', 'details'),
                      )
