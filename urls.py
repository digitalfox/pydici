from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Default to leads index
    (r'^$', 'pydici.leads.views.index'),

    # Admin
    (r'^admin/doc/', include('django.contrib.admindocs.urls')),
     (r'^admin/(.*)', admin.site.root),
     
    # Lead application
    (r'^leads/$', 'pydici.leads.views.index'),
    (r'^leads/csv_all$', 'pydici.leads.views.csv_all'),
    (r'^leads/csv_active$', 'pydici.leads.views.csv_active'),
    (r'^leads/(?P<lead_id>\d+)/$', 'pydici.leads.views.detail'),
    (r'^leads/mail$', 'pydici.leads.views.summary_mail'),
)
