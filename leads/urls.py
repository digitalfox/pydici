# -*- coding: UTF-8 -*-
"""URL dispatcher for lead module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import url
from leads.tables import LeadTableDT, ActiveLeadTableDT, RecentArchivedLeadTableDT, ClientCompanyLeadTableDT, LeadToBill, TagTableDT
import leads.views as v


leads_urls = [url(r'^review/?$', v.review, name="review"),
              url(r'^csv/(?P<target>.*)$', v.csv_export, name="csv_export"),
              url(r'^tag/(?P<tag_id>\d+)/$', v.tag, name="tag"),
              url(r'^tags/(?P<lead_id>\d+)$', v.tags, name="tags"),
              url(r'^tag/add$', v.add_tag, name="add_tag"),
              url(r'^tag/remove/(?P<tag_id>\d+)/(?P<lead_id>\d+)$', v.remove_tag, name="remove_tag"),
              url(r'^tag/manage$', v.manage_tags, name="manage_tags"),
              url(r'^(?P<lead_id>\d+)/$', v.detail, name="detail"),
              url(r'^leads$', v.leads, name="leads"),
              url(r'^lead$', v.lead, name="lead"),
              url(r'^lead/(?P<lead_id>\d+)/change$', v.lead, name="lead"),
              url(r'^lead/to_bill$', v.leads_to_bill, name="leads_to_bill"),
              url(r'^documents/(?P<lead_id>\d+)/$', v.lead_documents, name="lead_documents"),
              url(r'^sendmail/(?P<lead_id>\d+)/$', v.mail_lead, name="mail_lead"),
              url(r'^mail/text$', v.summary_mail, {"html": False}, name="summary_mail_text"),
              url(r'^mail/html$', v.summary_mail, {"html": True}, name="summary_mail_html"),
              url(r'^graph/bar-jqp$', v.graph_bar_jqp, name="graph_bar_jqp"),
              url(r'^graph/won-rate$', v.graph_leads_won_rate, name="graph_leads_won_rate"),
              url(r'^pivotable/$', v.leads_pivotable, name="leads-pivotable"),
              url(r'^pivotable/(?P<year>\d+)/$', v.leads_pivotable, name="leads-pivotable-year"),
              url(r'^pivotable/all$', v.leads_pivotable, {"year": "all"}, name="leads-pivotable-all"),
              url(r'^pivotable/lead/(?P<lead_id>\d+)$', v.lead_pivotable, name="lead_pivotable"),
              url(r'^datatable/all-lead/data/$', LeadTableDT.as_view(), name='lead_table_DT'),
              url(r'^datatable/active-lead/data/$', ActiveLeadTableDT.as_view(), name='active_lead_table_DT'),
              url(r'^datatable/recent-archived-lead/data/$', RecentArchivedLeadTableDT.as_view(), name='recent_archived_lead_table_DT'),
              url(r'^datatable/clientcompany-lead/(?P<clientcompany_id>\d+)/data/$', ClientCompanyLeadTableDT.as_view(), name='client_company_lead_table_DT'),
              url(r'^datatable/leads-to-bill/data/$', LeadToBill.as_view(), name='leads_to_bill_table_DT'),
              url(r'^datatable/all-tags/data/$', TagTableDT.as_view(), name='tag_table_DT'),
              ]
