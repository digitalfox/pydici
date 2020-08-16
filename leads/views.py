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
import codecs
from collections import defaultdict, OrderedDict


from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.utils.translation import ugettext as _
from django.utils.encoding import force_text
from django.db.models import Sum, Count, Min, Q
from django.views.decorators.cache import cache_page
from django.contrib.auth.decorators import permission_required
from django.db.models.query import QuerySet
from django.db.models.functions import TruncMonth
from django.conf import settings

from taggit.models import Tag, TaggedItem

from core.utils import send_lead_mail, sortedValues, COLORS, get_parameter, moving_average, nextMonth
from crm.utils import get_subsidiary_from_session
from leads.models import Lead
from leads.forms import LeadForm
from leads.utils import postSaveLead, leads_state_stat
from leads.utils import tag_leads_files, remove_lead_tag, merge_lead_tag
from leads.learn import compute_leads_state, compute_lead_similarity
from leads.learn import predict_tags, predict_similar
from core.utils import capitalize, getLeadDirs, createProjectTree, compact_text, get_fiscal_years_from_qs
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
    except Lead.DoesNotExist:
        raise Http404
    # Lead rank in active list
    subsidiary = get_subsidiary_from_session(request)
    active_leads = Lead.objects.active().order_by("creation_date")
    if subsidiary:
        active_leads = active_leads.filter(subsidiary=subsidiary)
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


    return render(request, "leads/lead_detail.html",
                  {"lead": lead,
                   "active_count": active_count,
                   "active_rank": rank + 1,
                   "next_lead": next_lead,
                   "previous_lead": previous_lead,
                   "link_root": reverse("core:index"),
                   "action_list": lead.get_change_history(),
                   "completion_url": reverse("leads:tags", args=[lead.id, ]),
                   "suggested_tags": suggestedTags,
                   "similar_leads": predict_similar(lead),
                   "enable_doc_tab": bool(settings.DOCUMENT_PROJECT_PATH),
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
            for field_name, field in list(form.fields.items()):
                if field_name in changed_fields and field_name not in blacklist_fields:
                    if field_name == "state":
                        state_changed = True
                    value = form.cleaned_data[field_name]
                    if field_name == "description":
                        if compact_text(value) == old_lead_description:
                            # Don't consider description field as changed if content is the same
                            continue
                    if isinstance(value, (list, QuerySet)):
                        value = ", ".join([str(i) for i in value])
                    else:
                        value = force_text(value)
                    value = value if len(value)<=max_length else value[0:max_length-3]+'...'
                    updated_fields.append("%s: %s" % (force_text(field.label or field_name), value))
            lead = form.save()
            postSaveLead(request, lead, updated_fields, created=created, state_changed=state_changed)
            return HttpResponseRedirect(reverse("leads:detail", args=[lead.id]))
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
    if clientDir is None:
        # Documents mechanism is disabled. This view should never been called..
        raise Http404

    lead_url_dir = settings.DOCUMENT_PROJECT_URL_DIR + leadDir[len(settings.DOCUMENT_PROJECT_PATH):]
    lead_url_file = settings.DOCUMENT_PROJECT_URL_FILE + leadDir[len(settings.DOCUMENT_PROJECT_PATH):]
    for directory in (businessDir, inputDir, deliveryDir):
        # Create project tree if at least one directory is missing
        if not os.path.exists(directory):
            createProjectTree(lead)
            break

    for directory in (businessDir, inputDir, deliveryDir):
        directoryName = directory.split("/")[-1]
        dirs = []
        files = []
        for fileName in os.listdir(directory):
            filePath = os.path.join(directory, fileName)
            fileName = fileName.encode('utf-8', 'surrogateescape').decode('utf-8', 'replace')  # fs encoding mixup
            if os.path.isdir(filePath):
                dirs.append((fileName + "/", lead_url_dir + "/" + directoryName + "/" + fileName + "/"))
            else:
                files.append((fileName, lead_url_file  + "/" + directoryName + "/" + fileName))
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
    response.write(codecs.BOM_UTF8)  # Poor excel needs tiger bom to understand UTF-8 easily

    writer = csv.writer(response, delimiter=';')
    writer.writerow([_("Name"), _("Client"), _("Description"), _("Managed by"), _("Salesman"), _("Starting"),
                                _("State"), _("Due date"), _("Staffing"), _("Sales (k€)"), _("Creation"),
                                _("Updated")])
    if target != "all":
        leads = Lead.objects.active()
    else:
        leads = Lead.objects.all()
    for lead in leads.order_by("creation_date"):
        state = lead.get_state_display()
        row = [lead.name, lead.client, lead.description, lead.responsible, lead.salesman, lead.start_date, state,
                         lead.due_date, lead.staffing_list(), lead.sales, lead.creation_date, lead.update_date]
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
    except Exception as e:
        return HttpResponse(_("Failed to send mail: %s") % e)


@pydici_non_public
@pydici_feature("leads")
def review(request):
    return render(request, "leads/review.html",
                  {"active_data_url": reverse('leads:active_lead_table_DT'),
                   "active_data_options": ''' "columnDefs": [{ "orderable": false, "targets": [5,8] },
                                                             { className: "hidden-xs hidden-sm hidden-md", "targets": [10,11,12]}],
                                               "pageLength": 25,
                                               "order": [[9, "asc"]] ''',
                   "recent_archived_data_url": reverse('leads:recent_archived_lead_table_DT'),
                   "recent_archived_data_options" : ''' "columnDefs": [{ "orderable": false, "targets": [5,8] },
                                                                       { className: "hidden-xs hidden-sm hidden-md", "targets": [10,11]}],
                                                         "order": [[9, "asc"]] ''',
                   "user": request.user})


@pydici_non_public
@pydici_feature("leads")
def leads(request):
    """All leads page"""
    return render(request, "leads/leads.html",
                  {"data_url" : reverse('leads:lead_table_DT'),
                   "user": request.user})


@pydici_non_public
@pydici_feature("leads")
def leads_to_bill(request):
    """All leads page"""
    return render(request, "leads/leads_to_bill.html",
                  {"data_url" : reverse('leads:leads_to_bill_table_DT'),
                   "datatable_options": ''' "columnDefs": [{ "orderable": false, "targets": [7,] }] ''',
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
        if settings.NEXTCLOUD_TAG_IS_ENABLED:
            tag_leads_files([lead.id])  # Update lead tags from lead files
        tag = Tag.objects.filter(name=tagName)[0]  # We should have only one, but in case of bad data, just take the first one
        answer["tag_url"] = reverse("leads:tag", args=[tag.id, ])
        answer["tag_remove_url"] = reverse("leads:remove_tag", args=[tag.id, lead.id])
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
        if settings.NEXTCLOUD_TAG_IS_ENABLED:
            remove_lead_tag(lead.id, tag.id)  # Remove the lead tag from the lead files
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
                if settings.NEXTCLOUD_TAG_IS_ENABLED:
                    merge_lead_tag(target_tag.name, tag.name)
                tag.delete()

    return render(request, "leads/manage_tags.html",
                  {"data_url": reverse('leads:tag_table_DT'),
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
@cache_page(60 * 60 * 24)
def graph_bar_jqp(request):
    """Nice graph bar of lead state during time using jqplot"""
    data = defaultdict(list)  # Raw data collected
    graph_data = []  # Data that will be returned to jqplot

    # Gathering data
    subsidiary = get_subsidiary_from_session(request)
    leads = Lead.objects.filter(creation_date__gt=date.today() - timedelta(3 * 365))
    if subsidiary:
        leads = leads.filter(subsidiary=subsidiary)
    for lead in leads:
        # Using first day of each month as key date
        kdate = date(lead.creation_date.year, lead.creation_date.month, 1)
        data[kdate].append(lead)

    if not data:
        return HttpResponse('')

    kdates = list(data.keys())
    kdates.sort()
    isoKdates = [a.isoformat() for a in kdates]  # List of date as string in ISO format

    # Draw a bar for each state
    for state in Lead.STATES:
        ydata = [len([i for i in x if i.state == state[0]]) for x in sortedValues(data)]
        ydata_detailed = [["%s (%s)" % (i.name, i.deal_id) for i in x if i.state == state[0]] for x in sortedValues(data)]
        graph_data.append(list(zip(isoKdates, ydata, ydata_detailed)))

    # Draw lead amount by month
    yAllLead = [float(sum([i.sales for i in x if i.sales])) for x in sortedValues(data)]
    yWonLead = [float(sum([i.sales for i in x if (i.sales and i.state == "WON")])) for x in sortedValues(data)]
    graph_data.append(list(zip(isoKdates, yAllLead)))
    graph_data.append(list(zip(isoKdates, yWonLead)))
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
@cache_page(60 * 60 * 24)
def graph_leads_won_rate(request):
    """Graph rates of won leads for given (or all) subsidiary"""
    graph_data = []
    start_date = (datetime.today() - timedelta(3 * 365))
    subsidiary = get_subsidiary_from_session(request)
    leads = Lead.objects.filter(creation_date__gt=start_date)
    if subsidiary:
        leads = leads.filter(subsidiary=subsidiary)
    leads = leads.annotate(month=TruncMonth("creation_date")).order_by("month")
    leads = leads.values("month", "state").annotate(Count("state"))
    leads_state = OrderedDict()
    won_rate = []
    months = []

    # compute lead state for each month
    for lead in leads:
        month = lead["month"]
        if month not in leads_state:
            leads_state[month] = {}
        leads_state[month][lead["state"]] = lead["state__count"]

    # compute won rate
    for month, lead_state in leads_state.items():
        if lead_state.get("WON", 0) > 0:
            won_rate.append(round(100* lead_state.get("WON", 0) / (lead_state.get("LOST", 0) +
                                                             lead_state.get("FORGIVEN", 0) +
                                                             lead_state.get("WON", 0)), 2))
            months.append(month.date().isoformat())

    if len(months) > 0:
        graph_data.append(["x"] + months)
        graph_data.append(["won-rate"] + won_rate)
        graph_data.append(["won-rate-MA90"] + moving_average(won_rate, 3, round_digits=2))
        graph_data.append(["won-rate-MA180"] + moving_average(won_rate, 6, round_digits=2))

    return render(request, "leads/graph_won_rate.html",
              {"graph_data": json.dumps(graph_data),
               "series_colors": COLORS,
               "user": request.user})


@pydici_non_public
@pydici_feature("reports")
@cache_page(60 * 60 * 24)
def graph_leads_pipe(request):
    """Graph in/out leads for given (or all) subsidiary"""
    graph_data = []
    input_count = {}
    input_amount = {}
    output_count = {}
    output_amount = {}
    output_states = ("WON", "LOST", "FORGIVEN", "SLEEPING")
    start_date = (datetime.today() - timedelta(3 * 365))
    subsidiary = get_subsidiary_from_session(request)
    leads = Lead.objects.filter(creation_date__gt=start_date)
    leads = leads.annotate(timesheet_start=Min("mission__timesheet__working_date"))
    if subsidiary:
        leads = leads.filter(subsidiary=subsidiary)

    for lead in leads:
        month = lead.creation_date.replace(day=1).date()
        input_count[month] = input_count.get(month, 0) + 1
        input_amount[month] = input_amount.get(month, 0) + (lead.sales or 0)
        if lead.state in output_states:
            out_date = lead.timesheet_start or lead.start_date or lead.update_date.date()
            out_date = out_date.replace(day=1)
            output_count[out_date] = output_count.get(out_date, 0) - 1
            output_amount[out_date] = output_amount.get(out_date, 0) - (lead.sales or 0)

    pipe_end_date = max(max(output_count.keys()), max(input_count.keys()))
    pipe_start_date = min(min(output_count.keys()), min(input_count.keys()))
    months = []
    month = pipe_start_date
    pipe_count = [0]  # start with fake 0 to allow sum with previous month
    pipe_amount = [0]
    while month <= pipe_end_date:
        months.append(month)
        pipe_count.append(pipe_count[-1] + input_count.get(month, 0) + output_count.get(month, 0))
        pipe_amount.append(pipe_amount[-1] + input_amount.get(month, 0) + output_amount.get(month, 0))
        month = nextMonth(month)
    # Remove fake zero
    pipe_count.pop(0)
    pipe_amount.pop(0)

    # Pad for month without data and switch to list of values
    input_count = [input_count.get(month, 0) for month in months]
    input_amount = [round(input_amount.get(month, 0)) for month in months]
    output_count = [output_count.get(month, 0) for month in months]
    output_amount = [round(output_amount.get(month, 0)) for month in months]

    # Compute offset by measuring pipe of last month
    current_leads = Lead.objects.exclude(state__in=output_states)
    if subsidiary:
        current_leads = current_leads.filter(subsidiary=subsidiary)
    offset_count = current_leads.count() - pipe_count[-1]
    pipe_count = [i + offset_count for i in pipe_count]
    offset_amount = (current_leads.aggregate(Sum("sales"))["sales__sum"] or 0) - pipe_amount[-1]
    pipe_amount = [round(i + offset_amount) for i in pipe_amount]

    graph_data.append(["x"] + [i.isoformat() for i in months])
    graph_data.append(["input_count"] + input_count)
    graph_data.append(["output_count"] + output_count)
    graph_data.append(["pipe_count"] + pipe_count)
    graph_data.append(["input_amount"] + input_amount)
    graph_data.append(["output_amount"] + output_amount)
    graph_data.append(["pipe_amount"] + pipe_amount)

    count_max = max([max(input_count), -max(output_count), max(pipe_count)])
    amount_max = max([max(input_amount), -max(output_amount), max(pipe_amount)])

    return render(request, "leads/graph_leads_pipe.html",
              {"graph_data": json.dumps(graph_data),
               "count_max": count_max,
               "amount_max": amount_max,
               "series_colors": COLORS,
               "user": request.user})


@pydici_non_public
@pydici_feature("reports")
@cache_page(60 * 60)
def graph_leads_activity(request):
    """some graph and figures about current leads activity"""
    subsidiary = get_subsidiary_from_session(request)

    # lead stat
    current_leads = Lead.objects.active()
    if subsidiary:
        current_leads = current_leads.filter(subsidiary=subsidiary)
    leads_state_data = leads_state_stat(current_leads)

    # lead creation rate
    first_lead_creation_date = Lead.objects.all().aggregate(Min("creation_date")).get("creation_date__min", datetime.now()).date()
    today = date.today()
    lead_creation_rate_data = []
    max_creation_rate = 0
    for timeframe in (30, 30*6, 365):
        start = today - timedelta(timeframe)
        if start > first_lead_creation_date:
            rate = Lead.objects.filter(creation_date__gte=start).count() / timeframe
            rate = round(rate, 2)
            lead_creation_rate_data.append([_("Lead rate last %s days" % timeframe), rate])
            max_creation_rate = max(rate, max_creation_rate)

    # lead duration
    leads = Lead.objects.filter(creation_date__gt=(datetime.today() - timedelta(3 * 365)))
    leads = leads.annotate(timesheet_start=Min("mission__timesheet__working_date"))
    if subsidiary:
        leads = leads.filter(subsidiary=subsidiary)
    leads_duration = defaultdict(list)
    for lead in leads:
        end_date = lead.timesheet_start or lead.start_date or lead.update_date.date()
        duration = (end_date - lead.creation_date.date()).days
        leads_duration[lead.creation_date.date().replace(day=1)].append(duration)

    # compute average
    leads_duration_data = [["x"] + [d.isoformat() for d in leads_duration.keys()]]
    leads_duration_data.append([_("duration")] + [sum(i)/len(i) for i in leads_duration.values()])

    return render(request, "leads/graph_leads_activity.html",
                  {"leads_state_data": leads_state_data,
                   "leads_state_title": _("Current leads"),
                   "lead_creation_rate_data": json.dumps(lead_creation_rate_data),
                   "max_creation_rate": max_creation_rate,
                   "leads_duration_data": json.dumps(leads_duration_data),
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
@cache_page(60 * 60 * 24)
def leads_pivotable(request, year=None):
    """Pivot table for all leads of given year"""
    data = []
    leads = Lead.objects.passive()
    subsidiary = get_subsidiary_from_session(request)
    if subsidiary:
        leads = leads.filter(subsidiary=subsidiary)
    derivedAttributes = """{'%s': $.pivotUtilities.derivers.bin('%s', 20),}""" % (_("sales (interval)"), _("sales (k€)"))
    month = int(get_parameter("FISCAL_YEAR_MONTH"))

    if not leads:
        return HttpResponse()

    years = get_fiscal_years_from_qs(leads, "creation_date")

    if year is None and years:
        year = years[-1]
    if year != "all":
        year = int(year)
        start = date(year, month, 1)
        end = date(year + 1, month, 1)
        leads = leads.filter(creation_date__gte=start, creation_date__lt=end)
    leads = leads.select_related("responsible", "client__contact", "client__organisation__company", "subsidiary",
                         "business_broker__company", "business_broker__contact")
    leads = leads.annotate(active_mission_count=Count('mission', filter=Q(mission__active=True)))
    for lead in leads:
        data.append({_("deal id"): lead.deal_id,
                     _("name"): lead.name,
                     _("client organisation"): str(lead.client.organisation),
                     _("client company"): str(lead.client.organisation.company),
                     _("sales (k€)"): int(lead.sales or 0),
                     _("date"): lead.creation_date.strftime("%Y-%m"),
                     _("responsible"): str(lead.responsible),
                     _("broker"): str(lead.business_broker),
                     _("state"): lead.get_state_display(),
                     _("billed (€)"): int(list(lead.clientbill_set.filter(state__in=("1_SENT", "2_PAID")).aggregate(Sum("amount")).values())[0] or 0),
                     _("Over budget margin (€)"): lead.margin(),
                     _("subsidiary"): str(lead.subsidiary),
                     _("active"): lead.active_mission_count > 0,
                     })
    return render(request, "leads/leads_pivotable.html", { "data": json.dumps(data),
                                                    "derivedAttributes": derivedAttributes,
                                                    "years": years,
                                                    "selected_year": year})
