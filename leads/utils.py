# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in Lead models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import  gettext
from django.contrib import messages
from django.contrib.admin.models import LogEntry, ADDITION, ContentType
from django.utils.encoding import force_text
from django.urls import reverse
from django.conf import settings
from django.utils.safestring import mark_safe
from django.db.models import Count

from taggit.models import Tag
from celery import shared_task

from leads.learn import compute_leads_state, compute_leads_tags, compute_lead_similarity
from staffing.models import Mission
from leads.models import StateProba, Lead
from core.utils import send_lead_mail, get_parameter, getLeadDirs


if settings.TELEGRAM_IS_ENABLED:
    import telegram

if settings.NEXTCLOUD_TAG_IS_ENABLED:
    import mysql.connector

# Nextcloud database queries
GET_TAG_ID = "SELECT id FROM oc_systemtag WHERE name=%s"
CREATE_TAG = "INSERT INTO oc_systemtag (name, visibility, editable) VALUES (%s, %s, %s)"
DELETE_TAG = "DELETE FROM oc_systemtag WHERE id=%s"
MERGE_FILE_TAGS = "UPDATE oc_systemtag_object_mapping SET objectid=%s, systemtagid=%s " \
                  "WHERE objectid=%s AND systemtagid=%s"
GET_FILES_ID_BY_DIR = "SELECT fc.fileid FROM oc_filecache fc " \
                      "INNER JOIN oc_mimetypes mt ON fc.mimetype = mt.id " \
                      "WHERE fc.path LIKE %s AND mt.mimetype NOT IN (%s) AND fc.storage=%s"
GET_FILES_ID_BY_TAG = "SELECT objectid FROM oc_systemtag_object_mapping WHERE systemtagid=%s"
TAG_FILE = "INSERT INTO oc_systemtag_object_mapping (objectid, objecttype, systemtagid) VALUES (%(file_id)s, %(object_type)s, %(tag_id)s) " \
           "ON DUPLICATE KEY UPDATE objectid=objectid"
UNTAG_FILE = "DELETE FROM oc_systemtag_object_mapping WHERE objectid=%(file_id)s AND objecttype=%(object_type)s AND systemtagid=%(tag_id)s"

def create_default_mission(lead):
    mission = Mission(lead=lead)
    mission.price = lead.sales  # Initialise with lead price
    mission.subsidiary = lead.subsidiary
    mission.responsible = lead.responsible
    try:
        mission.probability = lead.stateproba_set.get(state="WON").score
    except StateProba.DoesNotExist:
        # No state proba, leave mission proba default
        pass
    mission.save()
    # Create default staffing
    mission.create_default_staffing()
    return mission


def postSaveLead(request, lead, updated_fields, created=False, state_changed=False):
    mail = False
    if lead.send_email:
        mail = True
        lead.send_email = False

    lead.save()

    # Log it
    LogEntry.objects.log_action(
        user_id         = request.user.pk,
        content_type_id = ContentType.objects.get_for_model(lead).pk,
        object_id       = lead.pk,
        object_repr     = force_text(lead),
        action_flag     = ADDITION,
        change_message  = ", ".join(updated_fields),
    )

    if mail:
        try:
            fromAddr = request.user.email or "noreply@noreply.com"
            send_lead_mail(lead, request, fromAddr=fromAddr,
                           fromName="%s %s" % (request.user.first_name, request.user.last_name))
            messages.add_message(request, messages.INFO,  gettext("Lead sent to business mailing list"))
        except Exception as e:
            messages.add_message(request, messages.ERROR,  gettext("Failed to send mail: %s") % e)

    if settings.TELEGRAM_IS_ENABLED:
        try:
            bot = telegram.bot.Bot(token=settings.TELEGRAM_TOKEN)
            sticker = None
            url = get_parameter("HOST") + reverse("leads:detail", args=[lead.id, ])
            if created:
                msg = gettext("New Lead !\n%(lead)s\n%(url)s") % {"lead": lead, "url":url }
                sticker = settings.TELEGRAM_STICKERS.get("happy")
                chat_group = "new_leads"
            elif state_changed:
                # Only notify when lead state changed to avoid useless spam
                try:
                    change = "%s (%s)" % (lead.get_change_history()[0].change_message, lead.get_change_history()[0].user)
                except:
                    change = ""
                msg = gettext("Lead %(lead)s has been updated\n%(url)s\n%(change)s") % {"lead": lead, "url": url, "change": change}
                if lead.state == "WON":
                    sticker = settings.TELEGRAM_STICKERS.get("happy")
                elif lead.state in ("LOST", "FORGIVEN"):
                    sticker = settings.TELEGRAM_STICKERS.get("sad")
                chat_group = "leads_update"
            else:
                # No notification
                chat_group = msg = ""

            for chat_id in settings.TELEGRAM_CHAT.get(chat_group, []):
                bot.sendMessage(chat_id=chat_id, text=msg, disable_web_page_preview=True)
                if sticker:
                    bot.sendSticker(chat_id=chat_id, sticker=sticker)
        except Exception as e:
            messages.add_message(request, messages.ERROR,  gettext("Failed to send telegram notification: %s") % e)

    # Compute leads probability
    if lead.state in ("WON", "LOST", "SLEEPING", "FORGIVEN"):
        # Remove leads proba, no more needed
        lead.stateproba_set.all().delete()
        # Learn again. This new lead will now be used to training
        compute_leads_state.delay(relearn=True)
    else:
        # Just update proba for this lead with its new features
        compute_leads_state.delay(relearn=False, leads_id=[lead.id, ])

    # Update lead tags
    compute_leads_tags.delay()

    # update lead similarity model
    compute_lead_similarity.delay()

    # Create or update mission  if needed
    if lead.mission_set.count() == 0:
        if lead.state in ("OFFER_SENT", "NEGOTIATION", "WON"):
            create_default_mission(lead)
            messages.add_message(request, messages.INFO,  gettext("A mission has been initialized for this lead."))

    for mission in lead.mission_set.all():
        if mission.subsidiary != lead.subsidiary:
            mission.subsidiary = lead.subsidiary
            mission.save()
        if lead.state == "WON":
            mission.probability = 100
            mission.active = True
            mission.save()
            messages.add_message(request, messages.INFO,  gettext("Mission's probability has been set to 100%"))
        elif lead.state in ("LOST", "FORGIVEN", "SLEEPING"):
            mission.probability = 0
            mission.active = False
            mission.save()
            messages.add_message(request, messages.INFO,  gettext("According mission has been archived"))


@shared_task
def tag_leads_files(leads_id):
    """Tag all files of given leads.
    Can be called from tag views (when adding tags) or tag batch (for new files or initial sync)"""
    connection = None
    try:
        connection = connect_to_nextcloud_db()
        cursor = connection.cursor()

        for lead_id in leads_id:
            lead = Lead.objects.get(id=lead_id)
            # Get all the lead tags
            tags = lead.tags.all().values_list('name', flat=True)
            # Get document directories
            (client_dir, lead_dir, business_dir, input_dir, delivery_dir) = getLeadDirs(lead, with_prefix=False, create_dirs=False)
            tag_id_list = []
            for tag in tags:
                # Get the tag id in nextcloud database
                cursor.execute(GET_TAG_ID, (tag, ))
                rows = cursor.fetchall()
                if len(rows) == 0:
                    # Tag doesn't exist, we create it
                    cursor.execute(CREATE_TAG, (tag, "1", "1"))
                    tag_id = cursor.lastrowid
                else:
                    # Tag exists, fetch the first result
                    tag_id = rows[0][0]
                tag_id_list.append(tag_id)

            data_file_mapping = []
            for (directory_tag_name, directory) in ((settings.DOCUMENT_PROJECT_BUSINESS_DIR, business_dir),
                                                    (settings.DOCUMENT_PROJECT_DELIVERY_DIR, delivery_dir)):
                cursor.execute(GET_FILES_ID_BY_DIR, (directory+'%',
                                                     ",".join(settings.NEXTCLOUD_DB_EXCLUDE_TYPES),
                                                     settings.NEXTCLOUD_DB_FILE_STORAGE))
                files = cursor.fetchall()

                cursor.execute(GET_TAG_ID, (directory_tag_name, ))
                rows = cursor.fetchall()
                if len(rows) == 0:
                    # Tag doesn't exist, we create it
                    cursor.execute(CREATE_TAG, (directory_tag_name, "1", "1"))
                    directory_tag_id = cursor.lastrowid
                else:
                    # Tag exists, fetch the first result
                    directory_tag_id = rows[0][0]

                for file_id in files:
                    data_file_mapping.append({
                        'file_id': file_id[0],
                        'object_type': 'files',
                        'tag_id': directory_tag_id
                    })
                    for tag_id in tag_id_list:
                        data_file_mapping.append({
                            'file_id': file_id[0],
                            'object_type': 'files',
                            'tag_id': tag_id
                        })
            cursor.executemany(TAG_FILE, data_file_mapping)
            # Commit the changes to the database for each lead
            connection.commit()
    except Exception as e:
        raise e
    finally:
        if connection:
            connection.close()


@shared_task
def remove_lead_tag(lead_id, tag_id):
    """ Remove tag on given lead"""
    connection = None
    try:
        lead = Lead.objects.get(id=lead_id)
        tag_name = Tag.objects.get(id=tag_id).name
        connection = connect_to_nextcloud_db()
        cursor = connection.cursor()

        cursor.execute(GET_TAG_ID, (tag_name, ))
        rows = cursor.fetchall()
        if len(rows) == 0:
            # Tag doesn't exist, hence we don't do anything
            return
        else:
            # Tag exists, fetch the first result
            nextcloud_tag_id = rows[0][0]

        # Get document directories
        (client_dir, lead_dir, business_dir, input_dir, delivery_dir) = getLeadDirs(lead, with_prefix=False, create_dirs=False)
        # Find all files of the lead, except input
        cursor.execute(GET_FILES_ID_BY_DIR, (business_dir+'%',
                                             ",".join(settings.NEXTCLOUD_DB_EXCLUDE_TYPES),
                                             settings.NEXTCLOUD_DB_FILE_STORAGE))
        lead_files = cursor.fetchall()
        cursor.execute(GET_FILES_ID_BY_DIR, (delivery_dir+'%',
                                             ",".join(settings.NEXTCLOUD_DB_EXCLUDE_TYPES),
                                             settings.NEXTCLOUD_DB_FILE_STORAGE))
        lead_files.extend(cursor.fetchall())

        data_file_mapping = []
        for lead_file in lead_files:
            data_file_mapping.append({
                'file_id': lead_file[0],
                'object_type': 'files',
                'tag_id': nextcloud_tag_id
            })
        cursor.executemany(UNTAG_FILE, data_file_mapping)

        # Commit the changes to the database
        connection.commit()
    except Exception as e:
        raise e
    finally:
        if connection:
            connection.close()


@shared_task
def merge_lead_tag(target_tag_name, old_tag_name):
    """Propagate a tag merge on nextcloud tag system"""
    connection = None
    try:
        connection = connect_to_nextcloud_db()
        cursor = connection.cursor()

        # Get tag id from nextcloud definition table
        cursor.execute(GET_TAG_ID, (old_tag_name, ))
        old_tag_id = cursor.fetchall()[0][0]
        cursor.execute(GET_TAG_ID, (target_tag_name, ))
        target_tag_id = cursor.fetchall()[0][0]

        # Get all files with the previous tag to merge, and replace it with the target tag
        cursor.execute(GET_FILES_ID_BY_TAG, (old_tag_id, ))
        files_to_merge = []
        for file_id in cursor.fetchall():
            files_to_merge.append( (file_id[0], target_tag_id, file_id[0], old_tag_id) )
        # Merge existing tag link if it exists
        cursor.executemany(MERGE_FILE_TAGS, files_to_merge)

        # Delete the previous tag definition
        # TODO: Check that there is no more taggued files (example: in other nextcloud storage)
        cursor.execute(DELETE_TAG, (old_tag_id, ))

        # Commit the changes to the database
        connection.commit()
    except Exception as e:
        raise e
    finally:
        if connection:
            connection.close()


def connect_to_nextcloud_db():
    """Create a connexion to nextcloud database"""
    try:
        connection = mysql.connector.connect(host=settings.NEXTCLOUD_DB_HOST, database=settings.NEXTCLOUD_DB_DATABASE,
                                             user=settings.NEXTCLOUD_DB_USER, password=settings.NEXTCLOUD_DB_PWD)
        return connection
    except mysql.connector.Error as e:
        raise e


def leads_state_stat(leads):
    """Compute leads statistics in compatible C3.js format"""
    states = dict(Lead.STATES)
    leads_stat = leads.values("state").order_by("state").annotate(count=Count("state"))
    leads_stat = [[mark_safe(states[s['state']]), s['count']] for s in leads_stat]  # Use state label
    return leads_stat