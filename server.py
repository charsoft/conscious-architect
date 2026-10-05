import http.server
import socketserver
import json
import os
import sys
from datetime import datetime
from urllib.parse import unquote, urlsplit
from google.cloud import firestore
from content_policy import excluded, annotate
from research import analyze_video
from drafting import create_draft
from persistence import save_with_history
from transcription import store_uploaded_transcript

PORT = int(os.environ.get("PORT", 8080))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "gen-lang-client-0182092372")
STUDIO_PASSKEY = os.environ.get("STUDIO_PASSKEY", "ConsciousArchitect2026!")

# Initialize Firestore Client
try:
    db = firestore.Client(project=PROJECT_ID)
except Exception as e:
    print(f"[LOCAL DEV] Firestore client not initialized ({e}). Running in local mode.")
    db = None

class ConsciousArchitectHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def send_head(self):
        # Only browser assets are public; never expose backend/config/test files.
        path = unquote(urlsplit(self.path).path)
        if path not in ('/', '/index.html', '/draft-editor.js'):
            self.send_error(404, 'Not found')
            return None
        return super().send_head()

    def is_authenticated(self):
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:].strip()
            return token == STUDIO_PASSKEY
        return False

    def do_GET(self):
        if self.path == '/api/capabilities':
            if not self.is_authenticated():
                self.send_error(401, 'Unauthorized')
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'transcriptionEnabled': os.environ.get('TRANSCRIPTION_ENABLED') == 'true'}).encode('utf-8'))
            return
        if self.path == '/api/outliers':
            if not self.is_authenticated():
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Unauthorized'}).encode('utf-8'))
                return

            if db is None:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'outliers': []}).encode('utf-8'))
                return

            try:
                # Return every eligible candidate: the browser applies score/view filters.
                # A freshness-first cutoff would hide older high-scoring videos.
                docs = db.collection('trend_videos').stream()
                outliers, excluded_ids = [], []
                for snapshot in docs:
                    video = dict(snapshot.to_dict(), videoId=snapshot.id)
                    if excluded(video):
                        excluded_ids.append(snapshot.id)
                    else:
                        outliers.append(annotate(video))
                outliers.sort(key=lambda v: (v['stale'], -(v.get('outlierScore') or 0)))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'outliers': outliers, 'excludedIds': excluded_ids}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

        elif self.path == '/api/ideations':
            if not self.is_authenticated():
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Unauthorized'}).encode('utf-8'))
                return

            if db is None:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'ideations': []}).encode('utf-8'))
                return

            try:
                ideations_ref = db.collection('video_ideations').order_by('lastUpdated', direction=firestore.Query.DESCENDING).limit(50)
                docs = ideations_ref.stream()
                ideations = [d.to_dict() for d in docs]
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'ideations': ideations}).encode('utf-8'))
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
        if self.path == '/api/verify-key':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode('utf-8'))
                key = body.get('key', '').strip()
                if key == STUDIO_PASSKEY:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'valid': True, 'email': 'charlene@charsoft.com'}).encode('utf-8'))
                else:
                    self.send_response(403)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'valid': False, 'error': 'Invalid Master Studio Key'}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

        elif self.path == '/api/transcribe':
            if not self.is_authenticated():
                self.send_error(401, 'Unauthorized')
                return
            if os.environ.get('TRANSCRIPTION_ENABLED') != 'true':
                self.send_error(503, 'Transcription is disabled pending model-access verification')
                return
            if db is None:
                self.send_error(503, 'Transcription requires Firestore')
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 12 * 1024 * 1024:
                    raise ValueError('Upload request exceeds 12 MiB')
                result = store_uploaded_transcript(db, json.loads(self.rfile.read(length)))
                response = json.dumps(result).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(response)
            except ValueError as error:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(error)}).encode('utf-8'))
            except Exception as error:
                print(f'Transcription failed: {type(error).__name__}', flush=True)
                self.send_error(502, 'Transcription failed; no research findings were invented')

        elif self.path == '/api/draft':
            if not self.is_authenticated():
                self.send_error(401, 'Unauthorized')
                return
            if db is None:
                self.send_error(503, 'Drafting requires Firestore')
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 65536:
                    raise ValueError('Request must be 1–65536 bytes')
                result = create_draft(db, json.loads(self.rfile.read(length)))
                response = json.dumps(result).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(response)
            except ValueError as error:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(error)}).encode('utf-8'))
            except Exception as error:
                print(f'Drafting failed: {type(error).__name__}', flush=True)
                self.send_error(502, 'Draft generation failed; current script was not changed')

        elif self.path == '/api/research':
            if not self.is_authenticated():
                self.send_error(401, 'Unauthorized')
                return
            if db is None:
                self.send_error(503, 'Research requires Firestore')
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError('Invalid request size')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('Expected a request object')
                ids = body.get('videoIds')
                if not isinstance(ids, list) or not 1 <= len(ids) <= 3 or not all(isinstance(v, str) for v in ids):
                    raise ValueError('Select 1–3 videos per research request')
                results = []
                for video_id in dict.fromkeys(ids):
                    try:
                        results.append(analyze_video(db, video_id))
                    except Exception as error:
                        print(f'Research failed for {video_id}: {type(error).__name__}', flush=True)
                        results.append({'videoId': video_id, 'status': 'error',
                                        'reason': 'Caption retrieval or model analysis failed; no findings invented. Check service logs.'})
                response = json.dumps({'results': results}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(response)
            except (ValueError, TypeError):
                self.send_error(400, 'Invalid research request')

        elif self.path == '/api/save':
            if not self.is_authenticated():
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Unauthorized'}).encode('utf-8'))
                return

            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                doc_id = payload.get('ideationId', 'video-1-prompting-intentions')
                payload['lastUpdated'] = datetime.now().isoformat()
                
                # Write to Firestore if available
                if db:
                    save_with_history(db, doc_id, payload)
                
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
