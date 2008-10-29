from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Default to leads index
    (r'^$', 'pydici.leads.views.index'),

    # Admin
    (r'^leads/admin/doc/', include('django.contrib.admindocs.urls')),
     (r'^leads/admin/(.*)', admin.site.root),
     
    # Lead application
    (r'^leads/$', 'pydici.leads.views.index'),
    (r'^leads/csv/(.*)', 'pydici.leads.views.csv_export'),
    (r'^leads/(?P<lead_id>\d+)/$', 'pydici.leads.views.detail'),
    (r'^leads/sendmail/(?P<lead_id>\d+)/$', 'pydici.leads.views.mail_lead'),
    (r'^leads/mail/text', 'pydici.leads.views.summary_mail', { "html" : False }),
    (r'^leads/mail/html', 'pydici.leads.views.summary_mail', { "html" : True  }),
    (r'^leads/media/leads/(?P<path>.*)$', 'django.views.static.serve', {'document_root': '/home/fox/prog/workspace/pydici/media/leads/'}),
)