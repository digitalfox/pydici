# coding: utf-8
"""
Pydici leads views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import csv
from datetime import datetime, timedelta, date
import json
import os
import sys
from collections import defaultdict


from django.shortcuts import render
from django.core import urlresolvers
from django.http import HttpResponse, Http404
from django.utils.translation import ugettext as _
from django.db.models import Q
from django.views.decorators.cache import cache_page
from django.contrib.auth.decorators import permission_required

from taggit.models import Tag
from taggit_suggest.utils import suggest_tags
from django_tables2   import RequestConfig

from core.utils import send_lead_mail, sortedValues, COLORS
from leads.models import Lead
from leads.tables import LeadTable
import pydici.settings
from core.utils import capitalize, getLeadDirs, createProjectTree
from core.decorator import pydici_non_public



@pydici_non_public
def summary_mail(request, html=True):
    """Ready to copy/paste in mail summary leads activity"""
    today = datetime.today()
    delay = timedelta(days=6)  # Six days
    leads = []
    for state in ("WON", "FORGIVEN", "LOST", "SLEEPING", "WRITE_OFFER", "OFFER_SENT", "NEGOTIATION", "QUALIF"):
        rs = Lead.objects.filter(state=state).order_by("-update_date")
        if state in ("WON", "FORGIVEN", "LOST", "SLEEPING"):
            rs = rs.filter(update_date__gte=(today - delay))
        leads.append(rs)
    if html:
        return render(request, "leads/mail.html", {"lead_group": leads})
    else:
        return render(request, "leads/mail.txt", {"lead_group": leads}, content_type="text/plain; charset=utf-8")


@pydici_non_public
def detail(request, lead_id):
    """Lead detailed description"""
    try:
        lead = Lead.objects.get(id=lead_id)
        # Lead rank in active list
        active_leads = Lead.objects.active().order_by("creation_date")
        try:
            rank = [l.id for l in active_leads].index(lead.id)
            active_count = active_leads.count()
            if rank == 0:
                previous_lead = None
                next_lead = active_leads[1]
            elif rank + 1 >= active_count:
                previous_lead = active_leads[rank - 1]
                next_lead = None
            else:
                previous_lead = active_leads[rank - 1]
                next_lead = active_leads[rank + 1]
        except (ValueError, IndexError):
            # Lead is not in active list, rank it to zero
            rank = 0
            next_lead = None
            previous_lead = None
            active_count = None

        # Find suggested tags for this lead
        suggestedTags = set(suggest_tags(content=u"%s %s" % (lead.name, lead.description)))
        suggestedTags -= set(lead.tags.all())

    except Lead.DoesNotExist:
        raise Http404
    return render(request, "leads/lead_detail.html",
                  {"lead": lead,
                   "active_count": active_count,
                   "active_rank": rank + 1,
                   "next_lead": next_lead,
                   "previous_lead": previous_lead,
                   "link_root": urlresolvers.reverse("index"),
                   "action_list": lead.get_change_history(),
                   "completion_url": urlresolvers.reverse("leads.views.tags", args=[lead.id, ]),
                   "suggested_tags": suggestedTags,
                   "user": request.user})


@pydici_non_public
def lead_documents(request, lead_id):
    """Gather documents relative to this lead as a fragment page for an ajax call"""
    lead = Lead.objects.get(id=lead_id)
    documents = []  # List of name/url docs grouped by type
    clientDir, leadDir, businessDir, inputDir, deliveryDir = getLeadDirs(lead)
    leadDocURL = lead.getDocURL()
    for directory in (businessDir, inputDir, deliveryDir):
        # Create project tree if at least one directory is missing
        if not os.path.exists(directory):
            createProjectTree(lead)
            break

    for directory in (businessDir, inputDir, deliveryDir):
        directoryName = directory.split(u"/")[-1]
        dirs = []
        files = []
        for fileName in os.listdir(directory):
            filePath = os.path.join(directory.encode(sys.getfilesystemencoding()), fileName)
            if isinstance(fileName, str):
                # Corner case, files are not encoded with filesystem encoding but another...
                fileName = fileName.decode("utf8", "ignore")
            if os.path.isdir(filePath):
                dirs.append((fileName + u"/", leadDocURL + directoryName + u"/" + fileName + u"/"))
            else:
                files.append((fileName, leadDocURL + directoryName + u"/" + fileName))
        dirs.sort(key=lambda x: x[0])
        files.sort(key=lambda x: x[0])
        documents.append([directoryName, dirs + files])

    return render(request, "leads/lead_documents.html",
                  {"documents": documents,
                   "lead_doc_url": leadDocURL,
                   "user": request.user})


@pydici_non_public
def csv_export(request, target):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s" % _("leads.csv")
    writer = csv.writer(response, delimiter=';')
    writer.writerow([i.encode("ISO-8859-15") for i in [_("Name"), _("Client"), _("Description"),
                                                       _("Managed by"), _("Salesman"), _("Starting"),
                                                       _("State"), _("Due date"), _("Staffing"),
                                                       _(u"Sales (k€)"), _("Creation"),
                                                       _("Updated")]])
    if target != "all":
        leads = Lead.objects.active()
    else:
        leads = Lead.objects.all()
    for lead in leads.order_by("creation_date"):
        state = lead.get_state_display()
        row = [lead.name, lead.client, lead.description, lead.responsible, lead.salesman, lead.start_date, state,
                         lead.due_date, lead.staffing_list(), lead.sales, lead.creation_date, lead.update_date]
        row = [unicode(x).encode("ISO-8859-15", "ignore") for x in row]
        writer.writerow(row)
    return response


@pydici_non_public
def mail_lead(request, lead_id=0):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        raise Http404
    try:
        send_lead_mail(lead)
        return HttpResponse(_("Lead %(id)s was sent to %(mail)s !") % {"id": lead_id,
                                                                       "mail": pydici.settings.LEADS_MAIL_TO})
    except Exception, e:
        return HttpResponse(_("Failed to send mail: %s") % e)


@pydici_non_public
def review(request):
    today = datetime.today()
    delay = timedelta(days=10)  # (10 days)
    recentArchivedLeads = Lead.objects.passive().filter(Q(update_date__gte=(today - delay)) |
                                                      Q(state="SLEEPING"))
    recentArchivedLeads = recentArchivedLeads.order_by("state", "-update_date").select_related()
    recentArchivedLeadsTable = LeadTable(recentArchivedLeads)
    RequestConfig(request, paginate={"per_page": 50}).configure(recentArchivedLeadsTable)
    activeLeadsTable = LeadTable(Lead.objects.active().select_related().order_by("creation_date"))
    RequestConfig(request, paginate={"per_page": 50}).configure(activeLeadsTable)
    return render(request, "leads/review.html",
                  {"recent_archived_leads": recentArchivedLeads,
                   "recent_archived_leads_table": recentArchivedLeadsTable,
                   "active_leads_table": activeLeadsTable,
                   "user": request.user})


@pydici_non_public
def tag(request, tag_id):
    """Displays leads for given tag"""
    return render(request, "leads/tag.html",
                  {"leads": Lead.objects.filter(tags=tag_id),
                   "tag": Tag.objects.get(id=tag_id),
                   "user": request.user})


@pydici_non_public
@permission_required("leads.change_lead")
def add_tag(request):
    """Add a tag to a lead. Create the tag if needed"""
    answer = {}
    answer["tag_created"] = True  # indicate if a tag was reused or created
    answer["tag_url"] = ""  # url on tag
    answer["tag_name"] = ""  # tag name
    if request.POST["tag"]:
        tagName = capitalize(request.POST["tag"], keepUpper=True)
        lead = Lead.objects.get(id=int(request.POST["lead_id"]))
        if tagName in lead.tags.all().values_list("name", flat=True):
            answer["tag_created"] = False
        lead.tags.add(tagName)
        tag = Tag.objects.filter(name=tagName)[0]  # We should have only one, but in case of bad data, just take the first one
        answer["tag_url"] = urlresolvers.reverse("leads.views.tag", args=[tag.id, ])
        answer["tag_remove_url"] = urlresolvers.reverse("leads.views.remove_tag", args=[tag.id, lead.id])
        answer["tag_name"] = tag.name
        answer["id"] = tag.id
    return HttpResponse(json.dumps(answer), content_type="application/json")


@pydici_non_public
@permission_required("leads.change_lead")
def remove_tag(request, tag_id, lead_id):
    """Remove a tag to a lead"""
    answer = {}
    answer["error"] = False
    answer["id"] = tag_id
    try:
        tag = Tag.objects.get(id=tag_id)
        lead = Lead.objects.get(id=lead_id)
        lead.tags.remove(tag)
    except (Tag.DoesNotExist, Lead.DoesNotExist):
        answer["error"] = True
    return HttpResponse(json.dumps(answer), content_type="application/json")


@pydici_non_public
def tags(request, lead_id):
    """@return: all tags that contains q parameter and are not already associated to this lead as a simple text list"""
    tags = Tag.objects.all().exclude(lead__id=lead_id)  # Exclude existing tags
    tags = tags.filter(name__icontains=request.GET["q"])
    tags = tags.values_list("name", flat=True)
    return HttpResponse("\n".join(tags))


@pydici_non_public
@cache_page(60 * 10)
def graph_bar_jqp(request):
    """Nice graph bar of lead state during time using jqplot
    @todo: per year, with start-end date"""
    data = defaultdict(list)  # Raw data collected
    graph_data = []  # Data that will be returned to jqplot

    # Gathering data
    for lead in Lead.objects.filter(creation_date__gt=date.today() - timedelta(2 * 365)):
        # Using first day of each month as key date
        kdate = date(lead.creation_date.year, lead.creation_date.month, 1)
        data[kdate].append(lead)

    kdates = data.keys()
    kdates.sort()
    isoKdates = [a.isoformat() for a in kdates]  # List of date as string in ISO format

    # Draw a bar for each state
    for state in Lead.STATES:
        ydata = [len([i for i in x if i.state == state[0]]) for x in sortedValues(data)]
        graph_data.append(zip(isoKdates, ydata))

    # Draw lead amount by month
    yAllLead = [sum([i.sales for i in x if i.sales]) for x in sortedValues(data)]
    yWonLead = [sum([i.sales for i in x if (i.sales and i.state == "WON")]) for x in sortedValues(data)]
    graph_data.append(zip(isoKdates, yAllLead))
    graph_data.append(zip(isoKdates, yWonLead))
    if kdates:
        min_date = (kdates[0] - timedelta(30)).isoformat()
    else:
        min_date = ""

    return render(request, "leads/graph_bar_jqp.html",
                  {"graph_data": json.dumps(graph_data),
                   "series_label": [i[1] for i in Lead.STATES],
                   "series_colors": COLORS,
                   "min_date": min_date,
                   "user": request.user})
