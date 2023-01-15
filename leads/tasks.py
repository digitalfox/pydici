# coding: utf-8

"""
Module that handle asynchronous tasks
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from datetime import datetime, timedelta
import smtplib

from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext, pgettext
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.contrib.contenttypes.models import ContentType

from celery import shared_task
from taggit.models import Tag

from leads.learn import compute_leads_state, compute_leads_tags, compute_lead_similarity
from core.utils import get_parameter, audit_log_is_real_change, getLeadDirs
from leads.models import Lead

if settings.TELEGRAM_IS_ENABLED:
    import telegram

if settings.NEXTCLOUD_TAG_IS_ENABLED:
    import MySQLdb

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


@shared_task
def learning_warmup():
    """Warmup cache while people are sleeping to avoid punishing the first user of the day"""
    compute_leads_state.delay(relearn=True)
    compute_leads_tags.delay(relearn=True)
    compute_lead_similarity.delay(relearn=True)

@shared_task(bind=True)
def lead_mail_notify(self, lead_id, from_addr=None, from_name=None):
    """Notify (mail, telegram) about lead creation or status update"""
    lead = Lead.objects.get(id=lead_id)

    if not from_addr:
        pass
    if from_name:
       from_addr = f"{from_name} <{from_addr}>"

    url = get_parameter("HOST") + reverse("leads:lead", args=[lead.id, ]) + "?return_to=" + lead.get_absolute_url()
    subject = "[AVV] %s : %s (%s)" % (lead.client.organisation, lead.name, lead.deal_id)
    msgText = get_template("leads/lead_mail.txt").render(context={"obj": lead, "lead_url": url})
    msgHtml = get_template("leads/lead_mail.html").render(context={"obj": lead, "lead_url": url})
    msg = EmailMultiAlternatives(subject, msgText, from_addr, [get_parameter("LEAD_MAIL_TO"), ])
    msg.attach_alternative(msgHtml, "text/html")
    try:
        msg.send()
    except smtplib.SMTPException as e:
        raise self.retry(exc=e)


@shared_task(bind=True)
def lead_telegram_notify(self, lead_id, created=False, state_changed=False):
    lead = Lead.objects.get(id=lead_id)
    if not settings.TELEGRAM_IS_ENABLED:
        return
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
            change = ""
            for log in lead.history.filter(timestamp__gt=datetime.now()-timedelta(1/24)):
                for key, value in log.changes_display_dict.items():
                    if audit_log_is_real_change(value) and len(value) == 2:
                        change += f"{key}: {value[0]} → {value[1]} ({log.actor})\n".replace("None", "-")
                for key, value in log.changes_dict.items(): # Second loop for m2m
                    if len(value) == 3: # m2m changes
                        change += f"{key}: {pgettext('noun', value['operation'])} {', '.join(value['objects'])}\n"
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
    except telegram.TelegramError as e:
        raise self.retry(exc=e)


# Nextcloud tag tasks
def connect_to_nextcloud_db():
    """Create a connexion to nextcloud database"""
    try:
        connection = MySQLdb.connect(host=settings.NEXTCLOUD_DB_HOST, database=settings.NEXTCLOUD_DB_DATABASE,
                                     user=settings.NEXTCLOUD_DB_USER, password=settings.NEXTCLOUD_DB_PWD)
        return connection
    except MySQLdb.Error as e:
        raise e

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
        lead_files = list(cursor.fetchall())
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