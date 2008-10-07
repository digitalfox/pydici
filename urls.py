from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^pydici/', include('pydici.foo.urls')),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
     (r'^admin/(.*)', admin.site.root),
     
    # Lead application
    (r'^leads/$', 'pydici.leads.views.index'),
    (r'^leads/csv_all$', 'pydici.leads.views.csv_all'),
    (r'^leads/csv_active$', 'pydici.leads.views.csv_active'),
    (r'^leads/(?P<lead_id>\d+)/$', 'pydici.leads.views.detail'),
    (r'^leads/mail$', 'pydici.leads.views.mail'),
)
