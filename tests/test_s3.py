import io
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import session
from app.app import create_app
from app.s3 import upload_file, get_file_url, generate_safe_filename, delete_s3_objects
from werkzeug.datastructures import FileStorage

class TestS3Integration(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            'TESTING': True,
            'SECRET_KEY': 'test-secret',
            'DATABASE': os.path.join(os.path.dirname(__file__), 'test_temp.db'),
            'UPLOAD_FOLDER': os.path.join(os.path.dirname(__file__), 'temp_uploads')
        })
        self.client = self.app.test_client()
        os.makedirs(self.app.config['UPLOAD_FOLDER'], exist_ok=True)

    def tearDown(self):
        import shutil
        if os.path.exists(self.app.config['UPLOAD_FOLDER']):
            shutil.rmtree(self.app.config['UPLOAD_FOLDER'], ignore_errors=True)
        if os.path.exists(self.app.config['DATABASE']):
            try:
                os.remove(self.app.config['DATABASE'])
            except OSError:
                pass

    # 1. Unique filenames for repeated uploads with the same original filename
    def test_unique_filenames_for_repeated_uploads(self):
        name1 = generate_safe_filename("event_banner.jpg", prefix="poster")
        name2 = generate_safe_filename("event_banner.jpg", prefix="poster")
        self.assertNotEqual(name1, name2)
        self.assertTrue(name1.endswith(".jpg"))
        self.assertTrue(name2.endswith(".jpg"))

    # 2. Safe handling of long filenames and the VARCHAR(255) limit
    def test_long_filename_and_varchar255_fit(self):
        long_original = "a" * 350 + ".pdf"
        safe_name = generate_safe_filename(long_original, prefix="resume_1")
        
        # Test empty filename fallback as well
        empty_name = generate_safe_filename("", prefix="photo_1")
        self.assertIn("file", empty_name)
        
        bucket = "event-management-system-shailesh-2026-036019072884-us-east-1-an"
        full_s3_uri = f"s3://{bucket}/uploads/{safe_name}"
        
        # Must strictly fit inside VARCHAR(255)
        self.assertLessEqual(len(full_s3_uri), 255)

    # 3. Rejection of an s3:// URI referring to a different bucket
    @patch('app.s3.get_s3_client')
    def test_rejection_of_s3_uri_with_different_bucket(self, mock_get_client):
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        
        configured_bucket = 'event-management-system-shailesh-2026-036019072884-us-east-1-an'
        foreign_uri = "s3://unauthorized-foreign-bucket/uploads/secret.pdf"
        
        with patch.dict(os.environ, {'S3_BUCKET': configured_bucket}):
            with self.app.test_request_context():
                url = get_file_url(foreign_uri)
                self.assertEqual(url, "")
                # Must never generate presigned URL for an unauthorized bucket
                mock_s3.generate_presigned_url.assert_not_called()

    # 4. Successful presigned URL generation for the configured bucket
    @patch('app.s3.get_s3_client')
    def test_successful_presigned_url_generation_for_configured_bucket(self, mock_get_client):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.us-east-1.amazonaws.com/test-bucket/uploads/file.png?signed"
        mock_get_client.return_value = mock_s3
        
        bucket = 'event-management-system-shailesh-2026-036019072884-us-east-1-an'
        valid_uri = f"s3://{bucket}/uploads/poster.png"
        
        with patch.dict(os.environ, {'S3_BUCKET': bucket}):
            with self.app.test_request_context():
                url = get_file_url(valid_uri)
                self.assertEqual(url, "https://s3.us-east-1.amazonaws.com/test-bucket/uploads/file.png?signed")
                mock_s3.generate_presigned_url.assert_called_once_with(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': 'uploads/poster.png'},
                    ExpiresIn=900
                )

    # 5. Cleanup of earlier successful uploads when a later upload fails
    @patch('app.s3.get_s3_client')
    def test_cleanup_of_earlier_successful_uploads_on_later_failure(self, mock_get_client):
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        
        bucket = 'event-management-system-shailesh-2026-036019072884-us-east-1-an'
        
        # First call (poster) succeeds; second call (guest 1 photo) raises error
        call_count = [0]
        def side_effect_upload(fileobj, b, key, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                raise Exception("S3 network timeout during guest photo")
            return None
            
        mock_s3.upload_fileobj.side_effect = side_effect_upload
        
        # Setup sqlite db
        with self.app.app_context():
            import sqlite3
            conn = sqlite3.connect(self.app.config['DATABASE'])
            conn.execute("CREATE TABLE IF NOT EXISTS faculty_users (faculty_id INTEGER PRIMARY KEY, employee_id TEXT, email TEXT)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS event_tickets (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    faculty_id INTEGER,
                    event_name TEXT,
                    venue_status TEXT,
                    venue TEXT,
                    participants INTEGER,
                    event_date DATE,
                    event_time TIME,
                    poster TEXT,
                    status TEXT DEFAULT 'Pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("INSERT OR IGNORE INTO faculty_users VALUES (1, 'emp123', 'faculty@vit.edu')")
            conn.commit()
            conn.close()

        env = {'S3_BUCKET': bucket, 'AWS_REGION': 'us-east-1'}
        with patch.dict(os.environ, env):
            with self.client:
                with self.client.session_transaction() as sess:
                    sess['role'] = 'faculty'
                    sess['faculty_id'] = 1
                
                data = {
                    'event_name': 'DevOps Conference',
                    'venue_status': 'yes',
                    'venue': 'Hall A',
                    'event_date': '2026-11-20',
                    'event_time': '09:00',
                    'poster': (io.BytesIO(b'poster data'), 'poster.png'),
                    'guest_status': 'yes',
                    'guest_count': '1',
                    'guest_type_1': 'internal',
                    'guest_name_1': 'Dr. Alan',
                    'guest_phone_1': '9876543210',
                    'guest_photo_1': (io.BytesIO(b'failing photo'), 'photo.jpg')
                }
                response = self.client.post('/faculty/event/new', data=data, content_type='multipart/form-data')
                
                # S3 delete_objects should have been called to clean up the staged poster
                mock_s3.delete_objects.assert_called_once()
                call_args = mock_s3.delete_objects.call_args[1]
                self.assertEqual(call_args['Bucket'], bucket)
                deleted_keys = [o['Key'] for o in call_args['Delete']['Objects']]
                self.assertEqual(len(deleted_keys), 1)
                self.assertTrue(deleted_keys[0].startswith("uploads/"))

    # 6. Database rollback on upload failure
    @patch('app.s3.get_s3_client')
    def test_database_rollback_on_upload_failure(self, mock_get_client):
        mock_s3 = MagicMock()
        mock_s3.upload_fileobj.side_effect = Exception("AWS Outage")
        mock_get_client.return_value = mock_s3
        
        with self.app.app_context():
            import sqlite3
            conn = sqlite3.connect(self.app.config['DATABASE'])
            conn.execute("CREATE TABLE IF NOT EXISTS faculty_users (faculty_id INTEGER PRIMARY KEY, employee_id TEXT, email TEXT)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS event_tickets (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    faculty_id INTEGER,
                    event_name TEXT,
                    venue_status TEXT,
                    venue TEXT,
                    participants INTEGER,
                    event_date DATE,
                    event_time TIME,
                    poster TEXT,
                    status TEXT DEFAULT 'Pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("INSERT OR IGNORE INTO faculty_users VALUES (1, 'emp123', 'faculty@vit.edu')")
            conn.commit()
            conn.close()

        with patch.dict(os.environ, {'S3_BUCKET': 'my-bucket', 'AWS_REGION': 'us-east-1'}):
            with self.client:
                with self.client.session_transaction() as sess:
                    sess['role'] = 'faculty'
                    sess['faculty_id'] = 1
                
                data = {
                    'event_name': 'Failed Event',
                    'venue_status': 'yes',
                    'venue': 'Auditorium',
                    'event_date': '2026-12-01',
                    'event_time': '11:00',
                    'poster': (io.BytesIO(b'poster'), 'test.png')
                }
                self.client.post('/faculty/event/new', data=data, content_type='multipart/form-data')
                
                # Check DB was rolled back
                with self.app.app_context():
                    import sqlite3
                    conn = sqlite3.connect(self.app.config['DATABASE'])
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM event_tickets WHERE event_name = 'Failed Event'")
                    self.assertEqual(cur.fetchone()[0], 0)
                    conn.close()

    # 7. Local fallback when S3_BUCKET is unset
    def test_local_fallback_when_s3_bucket_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            if 'S3_BUCKET' in os.environ:
                del os.environ['S3_BUCKET']
            
            with self.app.app_context():
                file_obj = FileStorage(
                    stream=io.BytesIO(b"local content"),
                    filename="local.png",
                    content_type="image/png"
                )
                result = upload_file(file_obj, "saved_local.png")
                self.assertEqual(result, "saved_local.png")
                
                # File exists on local disk
                expected_path = os.path.join(self.app.config['UPLOAD_FOLDER'], "saved_local.png")
                self.assertTrue(os.path.exists(expected_path))

    # 8. Legacy local filename support
    def test_legacy_local_filename_support(self):
        local_filename = "legacy_test_image.jpg"
        full_path = os.path.join(self.app.config['UPLOAD_FOLDER'], local_filename)
        with open(full_path, 'wb') as f:
            f.write(b"image data")
            
        with self.app.test_request_context():
            url = get_file_url(local_filename)
            self.assertIn(f"/static/uploads/{local_filename}", url)

    # 9. Missing and malformed S3 references
    def test_missing_and_malformed_s3_references(self):
        with self.app.test_request_context():
            # None and empty
            self.assertEqual(get_file_url(None), "")
            self.assertEqual(get_file_url(""), "")
            
            # Malformed S3 URIs without key
            self.assertEqual(get_file_url("s3://"), "")
            self.assertEqual(get_file_url("s3://bucket-only"), "")
            self.assertEqual(get_file_url("s3:"), "")

    # 10. Existing template integration
    def test_existing_template_integration(self):
        with self.app.test_request_context():
            from flask import render_template_string
            rendered = render_template_string(
                '<img src="{{ file_url(poster) }}"><span>{{ resume | file_url }}</span>',
                poster="s3://event-management-system-shailesh-2026-036019072884-us-east-1-an/uploads/poster.jpg",
                resume=""
            )
            self.assertIn('<img src="', rendered)
            self.assertIn('<span></span>', rendered)

if __name__ == '__main__':
    unittest.main()
