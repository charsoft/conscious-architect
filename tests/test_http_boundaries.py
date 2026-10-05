import http.client
import threading
import unittest
from http.server import HTTPServer
from unittest.mock import patch

# Importing the handler must not contact production credentials or Firestore.
with patch('google.cloud.firestore.Client', return_value=None):
    import server


class HTTPBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd=HTTPServer(('127.0.0.1',0),server.ConsciousArchitectHandler)
        cls.thread=threading.Thread(target=cls.httpd.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown();cls.thread.join();cls.httpd.server_close()

    def request(self,path,method='GET',headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port,timeout=5)
        try:
            connection.request(method,path,headers=headers or {})
            response=connection.getresponse()
            return response.status,response.read()
        finally: connection.close()

    def test_public_browser_assets_and_health(self):
        for path in ('/','/index.html','/draft-editor.js','/api/health'):
            self.assertEqual(self.request(path)[0],200)

    def test_backend_files_and_directory_listing_are_blocked(self):
        for path in ('/server.py','/config/voice-v1.json','/.git/config','/tests/','/%73erver.py','/docs/'):
            self.assertEqual(self.request(path)[0],404)
        self.assertEqual(self.request('/server.py',method='HEAD')[0],404)

    def test_paid_endpoints_require_authentication(self):
        for path in ('/api/draft','/api/research','/api/transcribe'):
            self.assertEqual(self.request(path,method='POST')[0],401)

    def test_transcription_disabled_by_default(self):
        with patch.object(server,'STUDIO_PASSKEY','test-only'),patch.dict(server.os.environ,{'TRANSCRIPTION_ENABLED':'false'}):
            headers={'Authorization':'Bearer test-only'}
            status,body=self.request('/api/capabilities',headers=headers)
            self.assertEqual(status,200);self.assertIn(b'"transcriptionEnabled": false',body)
            self.assertEqual(self.request('/api/transcribe',method='POST',headers=headers)[0],503)


if __name__=='__main__':unittest.main()
