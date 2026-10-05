import yt_dlp
import os
import sys
from datetime import datetime, timedelta, timezone
from content_policy import classify
from radar_scoring import score_entries
from google.cloud import firestore

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "gen-lang-client-0182092372")
db = firestore.Client(project=PROJECT_ID)

CHANNELS = [
    '@YourYouniverse',
    '@7midas77',
    '@Krystle.Channel',
    '@CircleofAttraction',
    '@lavendaire',
    '@omnimindfulness',
    '@Michael.Bernard.Beckwith',
    '@BrianScott1111',
    '@yourhighervibes',
    '@CynthiaSueLarson',
    '@IntegralNaked'
]

def run_daily_sync():
    print(f"[{datetime.now().isoformat()}] Starting Daily Outlier Ingestion on {PROJECT_ID}...")
    today_str = datetime.now().strftime('%Y-%m-%d')
    now_iso = datetime.now(timezone.utc).isoformat()
    
    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
        'skip_download': True,
        'playlist_items': '1-15'
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for handle in CHANNELS:
            print(f"Scanning channel: {handle}")
            url = f"https://www.youtube.com/{handle}/videos"
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                print(f"  Error on {handle}: {e}")
                continue
                
            channel_title = info.get('channel') or info.get('uploader') or handle
            channel_id = info.get('channel_id') or handle
            entries = info.get('entries', [])
            
            if not entries:
                continue
                
            entries = list(entries)
            refs = [db.collection('trend_videos').document(e['id']) for e in entries if e.get('id')]
            previous = {snapshot.id: snapshot for snapshot in db.get_all(refs)} if refs else {}
            for entry in entries:
                prior = previous.get(entry.get('id'))
                old = prior.to_dict() if prior and prior.exists else {}
                entry['radarOverride'] = old.get('radarOverride')
                entry['upload_date'] = entry.get('upload_date') or old.get('publishedAt', '')
            scores = score_entries(entries)

            for e in entries:
                vid = e.get('id')
                if not vid:
                    continue
                    
                views = int(e.get('view_count') or 0)
                # Filter out statistical noise: require at least 2,500 views to qualify as a trend candidate
                if views < 2500:
                    continue

                duration = int(e.get('duration') or 0)
                score = scores[vid]
                outlier_score = score['outlierScore']
                
                doc_ref = db.collection('trend_videos').document(vid)
                doc_snap = previous[vid]
                
                delta_views = 0
                if doc_snap.exists:
                    old_views = doc_snap.to_dict().get('currentViews', 0)
                    delta_views = max(0, views - old_views)

                video_payload = {
                    'videoId': vid,
                    'title': e.get('title', ''),
                    'channelTitle': channel_title,
                    'channelHandle': handle,
                    'channelId': channel_id,
                    'publishedAt': e.get('upload_date', ''),
                    'durationSeconds': duration,
                    'isShort': duration > 0 and duration <= 60,
                    'thumbnailUrl': e.get('thumbnail') or f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg",
                    'descriptionSnippet': (e.get('description') or "")[:1000],
                    'currentViews': views,
                    **score,
                    'lastUpdated': now_iso,
                    **classify(e.get('title', ''))
                }
                # Human radarOverride fields are deliberately not overwritten.
                doc_ref.set(video_payload, merge=True)
                
                # Daily snapshot
                doc_ref.collection('snapshots').document(today_str).set({
                    'date': today_str,
                    'timestamp': now_iso,
                    'views': views,
                    'deltaViews24h': delta_views,
                    'outlierScore': outlier_score
                }, merge=True)

    print(f"[{datetime.now().isoformat()}] Daily sync complete!")

if __name__ == '__main__':
    run_daily_sync()
