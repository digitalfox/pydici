# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in Lead models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import ugettext
from django.contrib import messages
from django.contrib.admin.models import LogEntry, ADDITION, ContentType
from django.utils.encoding import force_unicode
from django.core import urlresolvers
from django.template.defaultfilters import slugify

from leads.learn import compute_leads_state, compute_leads_tags, compute_lead_similarity
from staffing.models import Mission
from leads.models import StateProba
from core.utils import send_lead_mail, get_parameter
from pydici.pydici_settings import TELEGRAM_IS_ENABLED, TELEGRAM_CHAT, TELEGRAM_TOKEN, TELEGRAM_STICKERS
from pydici.pydici_settings import NEXTCLOUD_TAG_IS_ENABLED, NEXTCLOUD_DATABASE
from pydici.pydici_settings import DOCUMENT_PROJECT_LEAD_DIR, DOCUMENT_PROJECT_DELIVERY_DIR, DOCUMENT_PROJECT_BUSINESS_DIR


if TELEGRAM_IS_ENABLED:
    import telegram

if NEXTCLOUD_TAG_IS_ENABLED:
    import mysql.connector

# Nextcloud database queries
REQUEST_TAG_ID = u"SELECT id FROM oc_systemtag st WHERE st.name = '{tag_name}'"
CREATE_TAG = u"INSERT INTO oc_systemtag (name, visibility, editable) VALUES (%s, %s, %s)"
REQUEST_FILES_ID = u"SELECT fileid FROM oc_filecache WHERE path LIKE 'client/%{lead_dir}/{first_level_dir}/%' AND mimetype <> 2 LIMIT 5"
TAG_FILE = (u"INSERT INTO oc_systemtag_object_mapping (objectid, objecttype, systemtagid) VALUES (%(file_id)s, %(object_type)s, %(tag_id)s) "
            u"ON DUPLICATE KEY UPDATE objectid=objectid")
UNTAG_FILE = u"DELETE FROM oc_systemtag_object_mapping WHERE objectid=%(file_id)s AND objecttype=%(object_type)s AND systemtagid=%(tag_id)s"


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


def postSaveLead(request, lead, updated_fields, created=False, state_changed=False, sync=False):
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
        object_repr     = force_unicode(lead),
        action_flag     = ADDITION,
        change_message  = ", ".join(updated_fields),
    )

    if mail:
        try:
            fromAddr = request.user.email or "noreply@noreply.com"
            send_lead_mail(lead, request, fromAddr=fromAddr,
                           fromName="%s %s" % (request.user.first_name, request.user.last_name))
            messages.add_message(request, messages.INFO, ugettext("Lead sent to business mailing list"))
        except Exception, e:
            messages.add_message(request, messages.ERROR, ugettext("Failed to send mail: %s") % e)

    if TELEGRAM_IS_ENABLED:
        try:
            bot = telegram.bot.Bot(token=TELEGRAM_TOKEN)
            sticker = None
            url = get_parameter("HOST") + urlresolvers.reverse("leads.views.detail", args=[lead.id, ])
            if created:
                msg = ugettext(u"New Lead !\n%(lead)s\n%(url)s") % {"lead": lead, "url":url }
                sticker = TELEGRAM_STICKERS.get("happy")
                chat_group = "new_leads"
            elif state_changed:
                # Only notify when lead state changed to avoid useless spam
                try:
                    change = u"%s (%s)" % (lead.get_change_history()[0].change_message, lead.get_change_history()[0].user)
                except:
                    change = u""
                msg = ugettext(u"Lead %(lead)s has been updated\n%(url)s\n%(change)s") % {"lead": lead, "url": url, "change": change}
                if lead.state == "WON":
                    sticker = TELEGRAM_STICKERS.get("happy")
                elif lead.state in ("LOST", "FORGIVEN"):
                    sticker = TELEGRAM_STICKERS.get("sad")
                chat_group = "leads_update"
            else:
                # No notification
                chat_group = ""

            for chat_id in TELEGRAM_CHAT.get(chat_group, []):
                bot.sendMessage(chat_id=chat_id, text=msg, disable_web_page_preview=True)
                if sticker:
                    bot.sendSticker(chat_id=chat_id, sticker=sticker)
        except Exception, e:
            messages.add_message(request, messages.ERROR, ugettext(u"Failed to send telegram notification: %s") % e)

    # Compute leads probability
    if sync:
        compute = compute_leads_state.now  # Select synchronous flavor of computation function
    else:
        compute = compute_leads_state

    if lead.state in ("WON", "LOST", "SLEEPING", "FORGIVEN"):
        # Remove leads proba, no more needed
        lead.stateproba_set.all().delete()
        # Learn again. This new lead will now be used to training
        compute(relearn=True)
    else:
        # Just update proba for this lead with its new features
        compute(relearn=False, leads_id=[lead.id,])

    # Update lead tags
    compute_leads_tags()

    # update lead similarity model
    compute_lead_similarity()

    # Create or update mission  if needed
    if lead.mission_set.count() == 0:
        if lead.state in ("OFFER_SENT", "NEGOTIATION", "WON"):
            create_default_mission(lead)
            messages.add_message(request, messages.INFO, ugettext("A mission has been initialized for this lead."))

    for mission in lead.mission_set.all():
        if mission.subsidiary != lead.subsidiary:
            mission.subsidiary = lead.subsidiary
            mission.save()
        if lead.state == "WON":
            mission.probability = 100
            mission.active = True
            mission.save()
            messages.add_message(request, messages.INFO, ugettext("Mission's probability has been set to 100%"))
        elif lead.state in ("LOST", "FORGIVEN", "SLEEPING"):
            mission.probability = 0
            mission.active = False
            mission.save()
            messages.add_message(request, messages.INFO, ugettext("According mission has been archived"))


def tag_leads_files(leads):
    """Tag all files of given leads.
    Can be called from tag views (when adding tags) or tag batch (for new files or initial sync)"""
    # TODO: make this a background task
    try:
        connection = connect_to_nextcloud_db()
        cursor = connection.cursor()

        for lead in leads:
            # Get all the lead tags
            tags = lead.tags.all().values_list('name', flat=True)
            for tag in tags:
                # Get the tag id in nextcloud database
                cursor.execute(REQUEST_TAG_ID.format(tag_name=tag))
                rows = cursor.fetchall()
                if len(rows) == 0:
                    # Tag doesn't exist, we create it
                    print(CREATE_TAG.format(tag, "1", "1"))
                    cursor.execute(CREATE_TAG, (tag, "1", "1"))
                    tag_id = cursor.lastrowid
                    print("Tag ", tag, " doesn't exist, created with id ", tag_id)
                else:
                    # Tag exists, fetch the first result
                    tag_id = rows[0][0]
                    print("Tag ", tag, " found, id: ", tag_id)

                # Find all business files of the lead
                lead_dir = DOCUMENT_PROJECT_LEAD_DIR.format(name=slugify(lead.name), deal_id=lead.deal_id)
                cursor.execute(REQUEST_FILES_ID.format(lead_dir=lead_dir,
                                                       first_level_dir=DOCUMENT_PROJECT_BUSINESS_DIR))
                lead_files = cursor.fetchall()

                cursor.execute(REQUEST_TAG_ID.format(tag_name=DOCUMENT_PROJECT_BUSINESS_DIR))
                rows = cursor.fetchall()
                if len(rows) == 0:
                    # Tag doesn't exist, we create it
                    cursor.execute(create_tag, (DOCUMENT_PROJECT_BUSINESS_DIR, "1", "1"))
                    business_tag_id = cursor.lastrowid
                else:
                    # Tag exists, fetch the first result
                    business_tag_id = rows[0][0]

                data_file_mapping = []
                for lead_file in lead_files:
                    print("Setting the tag : ", tag, " - ", tag_id, " on file ", lead_file[0])
                    data_file_mapping.append({
                        'file_id': lead_file[0],
                        'object_type': '"files"',
                        'tag_id': business_tag_id
                    })
                    data_file_mapping.append({
                        'file_id': lead_file[0],
                        'object_type': '"files"',
                        'tag_id': tag_id
                    })

                # Doing the same for delivery files
                cursor.execute(REQUEST_FILES_ID.format(lead_dir=lead_dir,
                                                       first_level_dir=DOCUMENT_PROJECT_DELIVERY_DIR))
                lead_files = cursor.fetchall()

                cursor.execute(REQUEST_TAG_ID.format(tag_name=DOCUMENT_PROJECT_DELIVERY_DIR))
                rows = cursor.fetchall()
                if len(rows) == 0:
                    # Tag doesn't exist, we create it
                    cursor.execute(create_tag, (DOCUMENT_PROJECT_DELIVERY_DIR, "1", "1"))
                    delivery_tag_id = cursor.lastrowid
                else:
                    # Tag exists, fetch the first result
                    delivery_tag_id = rows[0][0]

                data_file_mapping = []
                for lead_file in lead_files:
                    print("Setting the tag : ", tag, " - ", tag_id, " on file ", lead_file[0])
                    data_file_mapping.append({
                        'file_id': lead_file[0],
                        'object_type': '"files"',
                        'tag_id': delivery_tag_id
                    })
                    data_file_mapping.append({
                        'file_id': lead_file[0],
                        'object_type': '"files"',
                        'tag_id': tag_id
                    })
                cursor.executemany(TAG_FILE, data_file_mapping)

                # Commit the changes to the database
                connection.commit()
    finally:
        connection.close()


def remove_lead_tag(lead, tag):
    """ Remove tag on given lead"""
    try:
        connection = connect_to_nextcloud_db()
        cursor = connection.cursor()

        cursor.execute(REQUEST_TAG_ID.format(tag_name=tag))
        rows = cursor.fetchall()
        if len(rows) == 0:
            # Tag doesn't exist, hence we don't do anything
            return
        else:
            # Tag exists, fetch the first result
            tag_id = rows[0][0]
            print("Tag ", tag, " found, id: ", tag_id)

        # Find all files of the lead
        lead_dir = DOCUMENT_PROJECT_LEAD_DIR.format(name=slugify(lead.name), deal_id=lead.deal_id)
        cursor.execute(REQUEST_FILES_ID.format(lead_dir=lead_dir,
                                               first_level_dir=DOCUMENT_PROJECT_BUSINESS_DIR))
        lead_files = cursor.fetchall()
        cursor.execute(REQUEST_FILES_ID.format(lead_dir=lead_dir,
                                               first_level_dir=DOCUMENT_PROJECT_DELIVERY_DIR))
        lead_files.extend(cursor.fetchall())

        data_file_mapping = []
        for lead_file in lead_files:
            print("Removing the tag : ", tag, " - ", tag_id, " on file ", lead_file[0])
            data_file_mapping.append({
                'file_id': lead_file[0],
                'object_type': '"files"',
                'tag_id': tag_id
            })

        cursor.executemany(UNTAG_FILE, data_file_mapping)

        # Commit the changes to the database
        connection.commit()
    finally:
        connection.close()


def merge_lead_tag(old_tag, target_tag):
    """Propagate a tag merge on nextcloud tag system"""
    #TODO: update tag link table old_tag=>target_tag except if file already has link to target_tag
    pass


def connect_to_nextcloud_db():
    """Create a connexion to nextcloud database"""
    # TODO: get parameters on pydici settings
    # TODO: create database connexion, handle connection errors, return connection object
    try:
        connection = mysql.connector.connect(host="localhost", database=NEXTCLOUD_DATABASE,
                                             user="root", password="")
        print "Connected!"
        return connection
    except mysql.connector.Error as e:
        print "Error on mySQL connection" + e.msg
