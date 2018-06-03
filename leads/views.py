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
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.utils.translation import ugettext as _
from django.utils.encoding import force_text
from django.db.models import Sum
from django.views.decorators.cache import cache_page
from django.contrib.auth.decorators import permission_required
from django.db.models.query import QuerySet

from taggit.models import Tag, TaggedItem

from core.utils import send_lead_mail, sortedValues, COLORS, get_parameter
from leads.models import Lead
from leads.forms import LeadForm
from leads.utils import postSaveLead
from leads.learn import compute_leads_state, compute_lead_similarity
from leads.learn import predict_tags, predict_similar
import pydici.settings
from core.utils import capitalize, getLeadDirs, createProjectTree, compact_text, get_fiscal_years
from core.decorator import pydici_non_public, pydici_feature
from people.models import Consultant


@pydici_non_public
@pydici_feature("leads")
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
@pydici_feature("leads")
def detail(request, lead_id):
    """Lead detailed description"""
    try:
        lead = Lead.objects.select_related("client__contact", "client__organisation__company", "subsidiary").prefetch_related("mission_set").get(id=lead_id)
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

        # Find suggested tags for this lead except if it has already at least two tags
        tags = lead.tags.all()
        if tags.count() < 3:
            suggestedTags = set(predict_tags(lead))
            suggestedTags -= set(tags)
        else:
            suggestedTags = []

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
                   "similar_leads": predict_similar(lead),
                   "user": request.user})

@pydici_non_public
@pydici_feature("leads")
def lead(request, lead_id=None):
    """Lead creation or modification"""
    lead = None
    updated_fields = []
    state_changed = False
    blacklist_fields = ["creation_date", "tags"]
    max_length = 50
    old_lead_description = ""
    try:
        if lead_id:
            lead = Lead.objects.get(id=lead_id)
            old_lead_description  = lead.description
    except Lead.DoesNotExist:
        pass

    if request.method == "POST":
        if lead:
            form = LeadForm(request.POST, instance=lead)
            created = False
        else:
            form = LeadForm(request.POST)
            created = True
        if form.is_valid():
            changed_fields = form.changed_data
            for field_name, field in form.fields.items():
                if field_name in changed_fields and field_name not in blacklist_fields:
                    if field_name == "state":
                        state_changed = True
                    value = form.cleaned_data[field_name]
                    if field_name == "description":
                        if compact_text(value) == old_lead_description:
                            # Don't consider description field as changed if content is the same
                            continue
                    if isinstance(value, (list, QuerySet)):
                        value = ", ".join([unicode(i) for i in value])
                    else:
                        value = force_text(value)
                    value = value if len(value)<=max_length else value[0:max_length-3]+'...'
                    updated_fields.append("%s: %s" % (force_text(field.label or field_name), value))
            lead = form.save()
            postSaveLead(request, lead, updated_fields, created=created, state_changed=state_changed)
            return HttpResponseRedirect(urlresolvers.reverse("leads.views.detail", args=[lead.id]))
    else:
        if lead:
            form = LeadForm(instance=lead)  # A form that edit current lead
        else:
            try:
                consultant = Consultant.objects.get(trigramme__iexact=request.user.username)
                form = LeadForm(initial={"responsible": consultant})  # An unbound form
            except Consultant.DoesNotExist:
                form = LeadForm()  # An unbound form

    return render(request, "leads/lead.html", {"lead": lead,
                                               "form": form,
                                               "user": request.user})


@pydici_non_public
@pydici_feature("leads")
def lead_documents(request, lead_id):
    """Gather documents relative to this lead as a fragment page for an ajax call"""
    lead = Lead.objects.get(id=lead_id)
    documents = []  # List of name/url docs grouped by type
    clientDir, leadDir, businessDir, inputDir, deliveryDir = getLeadDirs(lead)
    lead_url_dir = pydici.settings.DOCUMENT_PROJECT_URL_DIR + leadDir[len(pydici.settings.DOCUMENT_PROJECT_PATH):]
    lead_url_file = pydici.settings.DOCUMENT_PROJECT_URL_FILE + leadDir[len(pydici.settings.DOCUMENT_PROJECT_PATH):]
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
                dirs.append((fileName + u"/", lead_url_dir + u"/" + directoryName + u"/" + fileName + u"/"))
            else:
                files.append((fileName, lead_url_file  + u"/" + directoryName + u"/" + fileName))
        dirs.sort(key=lambda x: x[0])
        files.sort(key=lambda x: x[0])
        documents.append([directoryName, dirs + files])

    return render(request, "leads/lead_documents.html",
                  {"documents": documents,
                   "lead_doc_url": lead_url_dir,
                   "user": request.user})


@pydici_non_public
@pydici_feature("leads")
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
@pydici_feature("leads")
def mail_lead(request, lead_id=0):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        raise Http404
    try:
        send_lead_mail(lead)
        return HttpResponse(_("Lead %(id)s was sent to %(mail)s !") % {"id": lead_id,
                                                                       "mail": get_parameter("LEAD_MAIL_TO")})
    except Exception, e:
        return HttpResponse(_("Failed to send mail: %s") % e)

@pydici_non_public
@pydici_feature("leads")
def review(request):
    return render(request, "leads/review.html",
                  {"active_data_url": urlresolvers.reverse('active_lead_table_DT'),
                   "active_data_options": ''' "columnDefs": [{ "orderable": false, "targets": [5,8] },
                                                             { className: "hidden-xs hidden-sm hidden-md", "targets": [10,11,12]}],
                                               "pageLength": 25,
                                               "order": [[9, "asc"]] ''',
                   "recent_archived_data_url": urlresolvers.reverse('recent_archived_lead_table_DT'),
                   "recent_archived_data_options" : ''' "columnDefs": [{ "orderable": false, "targets": [5,8] },
                                                                       { className: "hidden-xs hidden-sm hidden-md", "targets": [10,11]}],
                                                         "order": [[9, "asc"]] ''',
                   "user": request.user})


@pydici_non_public
@pydici_feature("leads")
def leads(request):
    """All leads page"""
    return render(request, "leads/leads.html",
                  {"data_url" : urlresolvers.reverse('lead_table_DT'),
                   "user": request.user})


@pydici_non_public
@pydici_feature("leads")
def tag(request, tag_id):
    """Displays leads for given tag"""

    return render(request, "leads/tag.html",
                  {"leads": Lead.objects.filter(tags=tag_id),
                   "tag": Tag.objects.get(id=tag_id),
                   "user": request.user})


@pydici_non_public
@pydici_feature("leads")
@permission_required("leads.change_lead")
def add_tag(request):
    """Add a tag to a lead. Create the tag if needed"""
    answer = {}
    answer["tag_created"] = True  # indicate if a tag was reused or created
    answer["tag_url"] = ""  # url on tag
    answer["tag_name"] = ""  # tag name
    if request.POST["tag"]:
        tagName = capitalize(request.POST["tag"])
        lead = Lead.objects.get(id=int(request.POST["lead_id"]))
        if tagName in lead.tags.all().values_list("name", flat=True):
            answer["tag_created"] = False
        lead.tags.add(tagName)
        if lead.state not in ("WON", "LOST", "FORGIVEN"):
            compute_leads_state(relearn=False, leads_id=[lead.id,])  # Update (in background) lead proba state as tag are used in computation
        compute_lead_similarity()  # update lead similarity model in background
        #TODO: call here tag_lead_files
        tag = Tag.objects.filter(name=tagName)[0]  # We should have only one, but in case of bad data, just take the first one
        answer["tag_url"] = urlresolvers.reverse("leads.views.tag", args=[tag.id, ])
        answer["tag_remove_url"] = urlresolvers.reverse("leads.views.remove_tag", args=[tag.id, lead.id])
        answer["tag_name"] = tag.name
        answer["id"] = tag.id
    return HttpResponse(json.dumps(answer), content_type="application/json")


@pydici_non_public
@pydici_feature("leads")
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
        if lead.state not in ("WON", "LOST", "FORGIVEN"):
            compute_leads_state(relearn=False, leads_id=[lead.id, ])  # Update (in background) lead proba state as tag are used in computation
        compute_lead_similarity()  # update lead similarity model in background
        # TODO: call here tag_lead_files
    except (Tag.DoesNotExist, Lead.DoesNotExist):
        answer["error"] = True
    return HttpResponse(json.dumps(answer), content_type="application/json")


@pydici_non_public
@pydici_feature("leads")
@permission_required("leads.change_lead")
def manage_tags(request):
    """Manage (rename, merge, remove) tags"""
    tags_to_merge = request.GET.get("tags_to_merge", None)
    if tags_to_merge:
        tags = []
        for tag_id in tags_to_merge.split(","):
            tags.append(Tag.objects.get(id=tag_id.split("-")[1]))
        if tags and len(tags)>1 :
            target_tag = tags[0]
            for tag in tags[1:]:
                TaggedItem.objects.filter(tag=tag).update(tag=target_tag)
                tag.delete()

    return render(request, "leads/manage_tags.html",
                  {"data_url": urlresolvers.reverse('tag_table_DT'),
                   "datatable_options": ''' "columnDefs": [{ "orderable": false, "targets": [0] }],
                                                             "order": [[1, "asc"]] ''',
                   "user": request.user})


@pydici_non_public
@pydici_feature("leads")
def tags(request, lead_id):
    """@return: all tags that contains q parameter and are not already associated to this lead as a simple text list"""
    tags = Tag.objects.all().exclude(lead__id=lead_id)  # Exclude existing tags
    tags = tags.filter(name__icontains=request.GET["term"])
    tags = tags.values_list("name", flat=True)
    return HttpResponse(json.dumps(list(tags)), content_type="application/json")


@pydici_non_public
@pydici_feature("leads")
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

    if not data:
        return HttpResponse('')

    kdates = data.keys()
    kdates.sort()
    isoKdates = [a.isoformat() for a in kdates]  # List of date as string in ISO format

    # Draw a bar for each state
    for state in Lead.STATES:
        ydata = [len([i for i in x if i.state == state[0]]) for x in sortedValues(data)]
        ydata_detailed = [["%s (%s)" % (i.name, i.deal_id) for i in x if i.state == state[0]] for x in sortedValues(data)]
        graph_data.append(zip(isoKdates, ydata, ydata_detailed))

    # Draw lead amount by month
    yAllLead = [float(sum([i.sales for i in x if i.sales])) for x in sortedValues(data)]
    yWonLead = [float(sum([i.sales for i in x if (i.sales and i.state == "WON")])) for x in sortedValues(data)]
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


@pydici_non_public
@pydici_feature("reports")
def lead_pivotable(request, lead_id=None):
    """Pivot table for a given lead with detail"""
    data = []
    dateFormat = "%Y%m%d"
    startDate = endDate = None
    try:
        startDate = request.GET.get("start", None)
        endDate = request.GET.get("end", None)
        if startDate:
            startDate = datetime.strptime(startDate, dateFormat)
        if endDate:
            endDate = datetime.strptime(endDate, dateFormat)
    except ValueError:
        pass

    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return Http404()
    for mission in lead.mission_set.all():
        data.extend(mission.pivotable_data(startDate=startDate, endDate=endDate))

    derivedAttributes = []

    return render(request, "leads/lead_pivotable.html", { "data": json.dumps(data),
                                                          "derivedAttributes": derivedAttributes,
                                                          "lead": lead,
                                                          "startDate": startDate,
                                                          "endDate": endDate
                                                          })


@pydici_non_public
@pydici_feature("reports")
def leads_pivotable(request, year=None):
    """Pivot table for all leads of given year"""
    data = []
    leads = Lead.objects.passive()
    derivedAttributes = """{'%s': $.pivotUtilities.derivers.bin('%s', 20),}""" % (_("sales (interval)"), _("sales"))
    month = int(get_parameter("FISCAL_YEAR_MONTH"))

    if not leads:
        return HttpResponse()

    years = get_fiscal_years(leads, "creation_date")

    if year is None and years:
        year = years[-1]
    if year != "all":
        year = int(year)
        start = date(year, month, 1)
        end = date(year + 1, month, 1)
        leads = leads.filter(creation_date__gte=start, creation_date__lt=end)
    leads = leads.select_related("responsible", "client__contact", "client__organisation__company", "subsidiary",
                         "business_broker__company", "business_broker__contact")
    for lead in leads:
        data.append({_("deal id"): lead.deal_id,
                     _("name"): lead.name,
                     _("client organisation"): unicode(lead.client.organisation),
                     _("client company"): unicode(lead.client.organisation.company),
                     _(u"sales (k€)"): int(lead.sales or 0),
                     _("date"): lead.creation_date.strftime("%Y-%m"),
                     _("responsible"): unicode(lead.responsible),
                     _("broker"): unicode(lead.business_broker),
                     _("state"): lead.get_state_display(),
                     _(u"billed (€)"): int(lead.clientbill_set.filter(state__in=("1_SENT", "2_PAID")).aggregate(Sum("amount")).values()[0] or 0),
                     _("subsidiary"): unicode(lead.subsidiary)})
    return render(request, "leads/leads_pivotable.html", { "data": json.dumps(data),
                                                    "derivedAttributes": derivedAttributes,
                                                    "years": years,
                                                    "selected_year": year})
