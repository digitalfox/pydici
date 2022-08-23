# -*- coding: UTF-8 -*-
"""URL dispatcher for lead module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.urls import re_path
from leads.tables import LeadTableDT, ActiveLeadTableDT, RecentArchivedLeadTableDT, ClientCompanyLeadTableDT, LeadToBill, TagTableDT
import leads.views as v


leads_urls = [ re_path(r'^review/?$', v.review, name="review"),
               re_path(r'^csv/(?P<target>.*)$', v.csv_export, name="csv_export"),
               re_path(r'^tag/(?P<tag_id>\d+)/$', v.tag, name="tag"),
               re_path(r'^tags/(?P<lead_id>\d+)$', v.tags, name="tags"),
               re_path(r'^tag/add$', v.add_tag, name="add_tag"),
               re_path(r'^tag/remove/(?P<tag_id>\d+)/(?P<lead_id>\d+)$', v.remove_tag, name="remove_tag"),
               re_path(r'^tag/manage$', v.manage_tags, name="manage_tags"),
               re_path(r'^(?P<lead_id>\d+)/$', v.detail, name="detail"),
               re_path(r'^leads$', v.leads, name="leads"),
               re_path(r'^lead$', v.lead, name="lead"),
               re_path(r'^lead/(?P<lead_id>\d+)/change$', v.lead, name="lead"),
               re_path(r'^lead/to_bill$', v.leads_to_bill, name="leads_to_bill"),
               re_path(r'^documents/(?P<lead_id>\d+)/$', v.lead_documents, name="lead_documents"),
               re_path(r'^sendmail/(?P<lead_id>\d+)/$', v.mail_lead, name="mail_lead"),
               re_path(r'^mail/text$', v.summary_mail, {"html": False}, name="summary_mail_text"),
               re_path(r'^mail/html$', v.summary_mail, {"html": True}, name="summary_mail_html"),
               re_path(r'^graph/bar-jqp$', v.graph_bar_jqp, name="graph_bar_jqp"),
               re_path(r'^graph/won-rate$', v.graph_leads_won_rate, name="graph_leads_won_rate"),
               re_path(r'^graph/leads-pipe$', v.graph_leads_pipe, name="graph_leads_pipe"),
               re_path(r'^graph/leads-activity$', v.graph_leads_activity, name="graph_leads_activity"),
               re_path(r'^pivotable/$', v.leads_pivotable, name="leads-pivotable"),
               re_path(r'^pivotable/(?P<year>\d+)/$', v.leads_pivotable, name="leads-pivotable-year"),
               re_path(r'^pivotable/all$', v.leads_pivotable, {"year": "all"}, name="leads-pivotable-all"),
               re_path(r'^pivotable/lead/(?P<lead_id>\d+)$', v.lead_pivotable, name="lead_pivotable"),
               re_path(r'^datatable/all-lead/data/$', LeadTableDT.as_view(), name='lead_table_DT'),
               re_path(r'^datatable/active-lead/data/$', ActiveLeadTableDT.as_view(), name='active_lead_table_DT'),
               re_path(r'^datatable/recent-archived-lead/data/$', RecentArchivedLeadTableDT.as_view(), name='recent_archived_lead_table_DT'),
               re_path(r'^datatable/clientcompany-lead/(?P<clientcompany_id>\d+)/data/$', ClientCompanyLeadTableDT.as_view(), name='client_company_lead_table_DT'),
               re_path(r'^datatable/leads-to-bill/data/$', LeadToBill.as_view(), name='leads_to_bill_table_DT'),
               re_path(r'^datatable/all-tags/data/$', TagTableDT.as_view(), name='tag_table_DT'),
              ]
