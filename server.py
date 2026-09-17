import http.server
import socketserver
import json
import os
import sys
from datetime import datetime
from google.cloud import firestore

PORT = int(os.environ.get("PORT", 8080))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "gen-lang-client-0182092372")

# Initialize Firestore Client
db = firestore.Client(project=PROJECT_ID)

class ConsciousArchitectHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path == '/api/outliers':
            try:
                videos_ref = db.collection('trend_videos').order_by('outlierScore', direction=firestore.Query.DESCENDING).limit(50)
                docs = videos_ref.stream()
                outliers = [d.to_dict() for d in docs]
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'outliers': outliers}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
        elif self.path == '/api/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'healthy', 'time': datetime.now().isoformat()}).encode('utf-8'))
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/save':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                doc_id = payload.get('ideationId', 'video-1-prompting-intentions')
                payload['lastUpdated'] = datetime.now().isoformat()
                
                # Write to Firestore
                db.collection('video_ideations').document(doc_id).set(payload, merge=True)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok', 'docId': doc_id, 'updatedAt': payload['lastUpdated']}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), ConsciousArchitectHandler) as httpd:
        print(f"The Conscious Architect Studio running on http://0.0.0.0:{PORT} (Project: {PROJECT_ID})")
        httpd.serve_forever()
