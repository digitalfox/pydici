# coding: utf-8
"""
Test cases for Lead module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.test import TestCase, override_settings
from django.urls import reverse
from django.test import RequestFactory
from django.contrib.messages.storage import default_storage
from django.contrib.auth.models import User
from django.conf import settings

from taggit.models import Tag

from people.models import Consultant
from leads.models import Lead
from staffing.models import Mission
from crm.models import Subsidiary, BusinessBroker, Client
from core.tests import PYDICI_FIXTURES, setup_test_user_features, TEST_USERNAME
from leads import learn as leads_learn
from leads.utils import post_save_lead
from leads.tasks import connect_to_nextcloud_db
from core.utils import getLeadDirs

from urllib.parse import urlsplit
import os.path
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import patch, call


class LeadModelTest(TestCase):
    fixtures = PYDICI_FIXTURES

    def setUp(self):
        setup_test_user_features()
        self.test_user = User.objects.get(username=TEST_USERNAME)
        if settings.DOCUMENT_PROJECT_PATH and not os.path.exists(settings.DOCUMENT_PROJECT_PATH):
            os.makedirs(settings.DOCUMENT_PROJECT_PATH)

    def test_create_lead(self):
        self.client.force_login(self.test_user)
        lead = create_lead()
        self.assertEqual(lead.staffing.count(), 0)
        self.assertEqual(lead.staffing_list(), ", (JCF)")
        lead.staffing.add(Consultant.objects.get(pk=1))
        self.assertEqual(lead.staffing.count(), 1)
        self.assertEqual(len(lead.update_date_strf()), 14)
        self.assertEqual(lead.staffing_list(), "SRE, (JCF)")
        self.assertEqual(lead.short_description(), "A wonderfull lead th...")
        self.assertEqual(reverse("leads:detail", args=[4]), "/leads/4/")

        url = "".join(urlsplit(reverse("leads:detail", args=[lead.id]))[2:])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        context = response.context[-1]
        self.assertEqual(str(context["lead"]), "World company : DSI  - laala")
        self.assertEqual(str(context["user"]), "sre")

    def test_save_lead(self):
        subsidiary = Subsidiary.objects.get(pk=1)
        broker = BusinessBroker.objects.get(pk=1)
        client = Client.objects.get(pk=1)
        lead = Lead(name="laalaa",
          state="QUALIF",
          client=client,
          salesman=None,
          description="A wonderfull lead that as a so so long description",
          subsidiary=subsidiary)
        deal_id = client.organisation.company.code, date.today().strftime("%y")
        self.assertEqual(lead.deal_id, "")  # No deal id code yet
        lead.save()
        self.assertEqual(lead.deal_id, "%s%s01" % deal_id)
        lead.paying_authority = broker
        lead.save()
        self.assertEqual(lead.deal_id, "%s%s01" % deal_id)
        lead.deal_id = ""
        lead.save()
        self.assertEqual(lead.deal_id, "%s%s02" % deal_id)  # 01 is already used

    def test_save_lead_and_active_client(self):
        lead = Lead.objects.get(id=1)
        lead.state = "LOST"
        lead.save()
        lead = Lead.objects.get(id=1)
        self.assertTrue(lead.client.active)  # There's still anotger active lead for this client
        otherLead = Lead.objects.get(id=3)
        otherLead.state = "SLEEPING"
        otherLead.save()
        lead = Lead.objects.get(id=1)
        self.assertFalse(lead.client.active)
        newLead = Lead()
        newLead.subsidiary_id = 1
        newLead.client = lead.client
        newLead.save()
        lead = Lead.objects.get(id=1)
        self.assertTrue(lead.client.active)  # A new lead on this client should mark it as active again

    def test_lead_done_work(self):
        for i in (1, 2, 3):
            lead = Lead.objects.get(id=i)
            a, b = lead.done_work()
            c, d = lead.done_work_k()
            e = lead.unattributed()
            f = lead.totalObjectiveMargin()
            g = lead.margin()
            for x in (a, b, c, d, e, f, g):
                self.assertIsInstance(x, (int, float, Decimal))

    def test_checkDoc(self):
        for i in (1, 2, 3):
            lead = Lead.objects.get(id=i)
            lead.checkDeliveryDoc()
            lead.checkBusinessDoc()


class LeadLearnTestCase(TestCase):
    """Test lead state proba learn"""
    fixtures = PYDICI_FIXTURES

    def test_state_model(self):
        if not leads_learn.HAVE_SCIKIT:
            return
        r1 = Consultant.objects.get(id=1)
        r2 = Consultant.objects.get(id=2)
        c1 = Client.objects.get(id=1)
        c2 = Client.objects.get(id=1)
        for i in range(20):
            a = create_lead()
            if a.id % 2:
                a.state = "WON"
                a.sales = a.id
                a.client = c1
                a.responsible = r1
            else:
                a.state = "FORGIVEN"
                a.sales = a.id
                a.client = c2
                a.responsible = r2
            a.save()
        leads_learn.eval_state_model(verbose=False)
        self.assertGreater(leads_learn.test_state_model(), 0.8, "Proba is too low")

    def test_tag_model(self):
        if not leads_learn.HAVE_SCIKIT:
            return
        for lead in Lead.objects.all():
            lead.tags.add("coucou")
            lead.tags.add("camembert")
        self.assertGreater(leads_learn.test_tag_model(), 0.8, "Probal is too low")

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_too_few_lead(self):
        f = RequestFactory()
        request = f.get("/")
        request.user = User.objects.get(id=1)
        request.session = {}
        request._messages = default_storage(request)
        lead = create_lead()
        post_save_lead(request, lead)  # Learn model cannot exist, but it should not raise error

    @patch("celery.app.task.Task.delay")
    def test_celery_jobs_are_called(self, mock_celery):
        f = RequestFactory()
        request = f.get("/")
        request.user = User.objects.get(id=1)
        request.session = {}
        request._messages = default_storage(request)
        lead = create_lead()
        post_save_lead(request, lead)
        mock_celery.assert_has_calls([call(relearn=False, leads_id=[lead.id]), call(), call()])

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_mission_proba(self):
        for i in range(5):
            # Create enough data to allow learn model to exist
            a = create_lead()
            a.state="WON"
            a.save()
        lead = Lead.objects.get(id=1)
        lead.state="LOST"  # Need more than one target class to build a solver
        lead.save()
        f = RequestFactory()
        request = f.get("/")
        request.user = User.objects.get(id=1)
        request.session = {}
        request._messages = default_storage(request)
        lead = create_lead()
        lead.state = "OFFER_SENT"
        lead.save()
        post_save_lead(request, lead)
        mission = lead.mission_set.all()[0]
        if leads_learn.HAVE_SCIKIT:
            self.assertEqual(mission.probability, lead.stateproba_set.get(state="WON").score)
        else:
            self.assertEqual(mission.probability, 50)
        lead.state = "WON"
        lead.save()
        post_save_lead(request, lead)
        mission = Mission.objects.get(id=mission.id)  # reload it
        self.assertEqual(mission.probability, 100)


@override_settings(NEXTCLOUD_DB_DATABASE="nextcloud_test")
class LeadNextcloudTagTestCase(TestCase):
    """Test lead tag on nextcloud file"""
    fixtures = PYDICI_FIXTURES

    def setUp(self):
        """Create the nextcloud file tables with init datas"""
        if not settings.NEXTCLOUD_TAG_IS_ENABLED:
            return
        if settings.DOCUMENT_PROJECT_PATH and not os.path.exists(settings.DOCUMENT_PROJECT_PATH):
            os.makedirs(settings.DOCUMENT_PROJECT_PATH)

        connection = None

        create_nextcloud_test_db()  # Create test db, if needed

        try:
            connection = connect_to_nextcloud_db()
            cursor = connection.cursor()

            # Verify that the table is not full first... just to "safely" drop table
            try:
                cursor.execute("SELECT COUNT(*) FROM oc_filecache")
                file_count = cursor.fetchall()
                if file_count[0][0] > 20:
                    self.fail("Appears that test database contains lots of file, aborting for safety")
            except:
                pass  # Table does not exist yet.
            # It's okay, it seems we are not in the production database, we can proceed


            create_nextcloud_tag_database(connection)

            # Create test data files for the 3 test leads
            create_file = "INSERT INTO oc_filecache (fileid, path, name, path_hash, storage, mimetype) " \
                          "VALUES (%s, %s, %s, %s, %s, 6)"
            for i in range(1, 3):
                lead = Lead.objects.get(id=i)
                (client_dir, lead_dir, business_dir, input_dir, delivery_dir) = getLeadDirs(lead, with_prefix=False, create_dirs=False)
                # Create 6 files per lead, 2 in each lead directory
                # With <file_id> like <lead_id> in first digit, and <file_id> in second digit
                files = [
                    (i*10, delivery_dir+"test1.txt", "test1.txt", i*10, settings.NEXTCLOUD_DB_FILE_STORAGE),
                    (i*10+1, delivery_dir+"test2.txt", "test2.txt", i*10+1, settings.NEXTCLOUD_DB_FILE_STORAGE),
                    (i*10+2, business_dir+"test3.txt", "test3.txt", i*10+2, settings.NEXTCLOUD_DB_FILE_STORAGE),
                    (i*10+3, business_dir+"test4.txt", "test4.txt", i*10+3, settings.NEXTCLOUD_DB_FILE_STORAGE),
                    (i*10+4, input_dir+"test5.txt",    "test5.txt", i*10+4, settings.NEXTCLOUD_DB_FILE_STORAGE),
                    (i*10+5, input_dir+"test6.txt",    "test6.txt", i*10+5, settings.NEXTCLOUD_DB_FILE_STORAGE)
                ]
                cursor.executemany(create_file, files)
            connection.commit()
        finally:
            if connection:
                connection.close()

    def test_tag_and_remove_tag_file(self):
        if not settings.NEXTCLOUD_TAG_IS_ENABLED:
            return
        from leads.tasks import connect_to_nextcloud_db, tag_leads_files, remove_lead_tag, merge_lead_tag, GET_TAG_ID
        connection = None
        try:
            connection = connect_to_nextcloud_db()
            cursor = connection.cursor()
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")

            lead1 = Lead.objects.get(id=1)
            lead1.tags.add("A test tag")
            lead1.tags.add("Another tag")
            tag1 = Tag.objects.get(name="A test tag")
            tag2 = Tag.objects.get(name="Another tag")
            # Tag another lead for non impact test
            lead2 = Lead.objects.get(id=2)
            lead2.tags.add("A test tag")

            # The function to be tested
            tag_leads_files([lead1.id, lead2.id])

            # Test the 6 lead file tags of lead 1
            expected_tags1 = [
                ["A test tag", "Another tag", settings.DOCUMENT_PROJECT_DELIVERY_DIR],
                ["A test tag", "Another tag", settings.DOCUMENT_PROJECT_DELIVERY_DIR],
                ["A test tag", "Another tag", settings.DOCUMENT_PROJECT_BUSINESS_DIR],
                ["A test tag", "Another tag", settings.DOCUMENT_PROJECT_BUSINESS_DIR],
                [],
                []
            ]
            for i, expected_tag in enumerate(expected_tags1):
                self.assertEqual(expected_tag, collect_file_tags(connection, 10+i))

            # Test the 6 lead file tags of lead 2
            expected_tags2 = [
                ["A test tag", settings.DOCUMENT_PROJECT_DELIVERY_DIR],
                ["A test tag", settings.DOCUMENT_PROJECT_DELIVERY_DIR],
                ["A test tag", settings.DOCUMENT_PROJECT_BUSINESS_DIR],
                ["A test tag", settings.DOCUMENT_PROJECT_BUSINESS_DIR],
                [],
                []
            ]
            for i, expected_tag in enumerate(expected_tags2):
                self.assertEqual(expected_tag, collect_file_tags(connection, 20+i))

            # Also test that the third lead doesn't have file tags
            for i in range(6):
                self.assertListEqual(collect_file_tags(connection, 30+i), [])

            # Now remove a tag
            remove_lead_tag(lead1.id, tag1.id)

            # Test that it is actually removed on lead 1
            expected_tags1 = [
                ["Another tag", settings.DOCUMENT_PROJECT_DELIVERY_DIR],
                ["Another tag", settings.DOCUMENT_PROJECT_DELIVERY_DIR],
                ["Another tag", settings.DOCUMENT_PROJECT_BUSINESS_DIR],
                ["Another tag", settings.DOCUMENT_PROJECT_BUSINESS_DIR],
                [],
                []
            ]
            for i, expected_tag in enumerate(expected_tags1):
                self.assertEqual(expected_tag, collect_file_tags(connection, 10+i))

            # Test we didn't impact lead 2
            for i, expected_tag in enumerate(expected_tags2):
                self.assertEqual(expected_tag, collect_file_tags(connection, 20+i))

            # Test the merge of the two tags
            merge_lead_tag("A test tag", "Another tag")

            # Test that lead 1 has "A test tag" rather than "Another tag" (as lead 2 in fact...)
            for i, expected_tag in enumerate(expected_tags2):
                self.assertEqual(expected_tag, collect_file_tags(connection, 10 + i))

            # Test we didn't impact lead 2
            for i, expected_tag in enumerate(expected_tags2):
                self.assertEqual(expected_tag, collect_file_tags(connection, 20 + i))

            # Test that lead old lead tag is removed
            cursor.execute(GET_TAG_ID, ("Another tag", ))
            self.assertEqual(len(cursor.fetchall()), 0)

            cursor.close()
        finally:
            if connection:
                connection.close()


def create_lead():
    """Create test lead
    @return: lead object"""
    lead = Lead(name="laala",
          due_date=date(2008,11,0o1),
          update_date=datetime(2008, 11, 1, 15,55,40),
          creation_date=datetime(2008, 11, 1, 15,43,43),
          start_date=date(2008, 11, 0o1),
          responsible=None,
          sales=None,
          external_staffing="JCF",
          state="QUALIF",
          deal_id="123456",
          client=Client.objects.get(pk=1),
          salesman=None,
          description="A wonderfull lead that as a so so long description",
          subsidiary=Subsidiary.objects.get(pk=1))

    lead.save()
    return lead


def create_nextcloud_tag_database(connection):
    """Create the test nextcloud database and the 3 tables used for file tagging:
    - oc_filecache: the file index
    - oc_systemtag: the tag definition
    - oc_systemtag_object_mapping: the link between file(s) and tag(s)
    """
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("DROP TABLE IF EXISTS `oc_filecache`;")
        create_nextcloud_file_table = """
        CREATE TABLE `oc_filecache` (
          `fileid` bigint(20) NOT NULL AUTO_INCREMENT,
          `storage` bigint(20) NOT NULL DEFAULT '0',
          `path` varchar(4000) COLLATE utf8_bin DEFAULT NULL,
          `path_hash` varchar(32) COLLATE utf8_bin NOT NULL DEFAULT '',
          `parent` bigint(20) NOT NULL DEFAULT '0',
          `name` varchar(250) COLLATE utf8_bin DEFAULT NULL,
          `mimetype` bigint(20) NOT NULL DEFAULT '0',
          `mimepart` bigint(20) NOT NULL DEFAULT '0',
          `size` bigint(20) NOT NULL DEFAULT '0',
          `mtime` bigint(20) NOT NULL DEFAULT '0',
          `storage_mtime` bigint(20) NOT NULL DEFAULT '0',
          `encrypted` int(11) NOT NULL DEFAULT '0',
          `unencrypted_size` bigint(20) NOT NULL DEFAULT '0',
          `etag` varchar(40) COLLATE utf8_bin DEFAULT NULL,
          `permissions` int(11) DEFAULT '0',
          `checksum` varchar(255) COLLATE utf8_bin DEFAULT NULL,
          PRIMARY KEY (`fileid`),
          UNIQUE KEY `fs_storage_path_hash` (`storage`,`path_hash`),
          KEY `fs_parent_name_hash` (`parent`,`name`),
          KEY `fs_storage_mimetype` (`storage`,`mimetype`),
          KEY `fs_storage_mimepart` (`storage`,`mimepart`),
          KEY `fs_storage_size` (`storage`,`size`,`fileid`),
          KEY `fs_mtime` (`mtime`)
        ) ENGINE=InnoDB AUTO_INCREMENT=341112 DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
        """
        cursor.execute(create_nextcloud_file_table)

        cursor.execute("DROP TABLE IF EXISTS `oc_systemtag`;")
        create_nextcloud_tag_table = """
        CREATE TABLE `oc_systemtag` (
          `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
          `name` varchar(64) COLLATE utf8_bin NOT NULL DEFAULT '',
          `visibility` smallint(6) NOT NULL DEFAULT '1',
          `editable` smallint(6) NOT NULL DEFAULT '1',
          PRIMARY KEY (`id`),
          UNIQUE KEY `tag_ident` (`name`,`visibility`,`editable`)
        ) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
        """
        cursor.execute(create_nextcloud_tag_table)

        cursor.execute("DROP TABLE IF EXISTS `oc_systemtag_object_mapping`;")
        create_nextcloud_file_tag_table = """
        CREATE TABLE `oc_systemtag_object_mapping` (
          `objectid` varchar(64) COLLATE utf8_bin NOT NULL DEFAULT '',
          `objecttype` varchar(64) COLLATE utf8_bin NOT NULL DEFAULT '',
          `systemtagid` bigint(20) unsigned NOT NULL DEFAULT '0',
          UNIQUE KEY `mapping` (`objecttype`,`objectid`,`systemtagid`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
        """
        cursor.execute(create_nextcloud_file_tag_table)

        cursor.execute("DROP TABLE IF EXISTS `oc_mimetypes`;")
        create_nextcloud_mimetypes_table = """
        CREATE TABLE `oc_mimetypes`(
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `mimetype` varchar(255) COLLATE utf8_bin NOT NULL DEFAULT '',
            PRIMARY KEY(`id`),
            UNIQUE KEY `mimetype_id_index`(`mimetype`)
        ) ENGINE = InnoDB AUTO_INCREMENT = 65 DEFAULT CHARSET = utf8 COLLATE = utf8_bin;
        """
        cursor.execute(create_nextcloud_mimetypes_table)

        create_mimetypes_data = """
        INSERT INTO `oc_mimetypes`
        VALUES (3, 'application'), (29, 'application/font-sfnt'), (43, 'application/font-woff'),
               (51, 'application/gpx+xml'), (47, 'application/illustrator'), (55, 'application/internet-shortcut'),
               (13, 'application/javascript'), (4, 'application/json'), (34, 'application/msword'), 
               (14, 'application/octet-stream'), (8, 'application/pdf'), (54, 'application/vnd.garmin.tcx+xml'), 
               (52, 'application/vnd.google-earth.kml+xml'), (53, 'application/vnd.google-earth.kmz'), 
               (31, 'application/vnd.ms-excel'), (58, 'application/vnd.ms-excel.sheet.macroEnabled.12'), 
               (42, 'application/vnd.ms-fontobject'), (39, 'application/vnd.ms-powerpoint'), 
               (7, 'application/vnd.oasis.opendocument.text'), 
               (23, 'application/vnd.openxmlformats-officedocument.presentationml.presentation'), 
               (62, 'application/vnd.openxmlformats-officedocument.presentationml.template'), 
               (19, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'), 
               (24, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'), 
               (60, 'application/x-7z-compressed'), (36, 'application/x-gimp'), (15, 'application/x-gzip'), 
               (38, 'application/x-iwork-keynote-sffkey'), (21, 'application/x-iwork-pages-sffpages'), 
               (40, 'application/x-photoshop'), (35, 'application/x-php'), (44, 'application/x-shockwave-flash'), 
               (22, 'application/x-tex'), (63, 'application/xml'), (33, 'application/zip'), (45, 'audio'), 
               (56, 'audio/mpegurl'), (46, 'audio/wav'), (57, 'audio/x-scpls'), (1, 'httpd'), (2, 'httpd/unix-directory'), 
               (11, 'image'), (25, 'image/bmp'), (30, 'image/gif'), (12, 'image/jpeg'), (18, 'image/png'), 
               (17, 'image/svg+xml'), (50, 'image/x-dcraw'), (5, 'text'), (16, 'text/css'), (27, 'text/html'), 
               (20, 'text/markdown'), (6, 'text/plain'), (37, 'text/rtf'), (32, 'text/x-c++src'), (26, 'text/x-h'), 
               (28, 'text/x-shellscript'), (9, 'video'), (10, 'video/mp4'), (41, 'video/mpeg'), (49, 'video/quicktime'), 
               (48, 'video/x-msvideo');
        """
        cursor.execute(create_mimetypes_data)
        
        connection.commit()
    finally:
        if cursor:
            cursor.close()


def collect_file_tags(connection, file_id):
    """"Collect file tags and return them formatted in a sorted list"""
    get_file_tag_names = "SELECT st.name " \
                         "FROM oc_systemtag_object_mapping om " \
                         "INNER JOIN oc_systemtag st ON st.id = om.systemtagid " \
                         "WHERE om.objectid = %s"
    cursor = connection.cursor()
    cursor.execute(get_file_tag_names, (file_id,))

    file_tags = cursor.fetchall()

    # Format into a sorted list
    actual_file_lead_tags = [j[0] for j in file_tags]
    actual_file_lead_tags.sort()
    cursor.close()
    return actual_file_lead_tags


def create_nextcloud_test_db():
    """Create if needed, test database for nextcloud"""
    import MySQLdb
    connection = MySQLdb.connect(host=settings.NEXTCLOUD_DB_HOST,
                                 user=settings.NEXTCLOUD_DB_USER, password=settings.NEXTCLOUD_DB_PWD)
    cursor = connection.cursor()
    cursor.execute("""create database if not exists %s""" % settings.NEXTCLOUD_DB_DATABASE)
    cursor.close()
    connection.close()
