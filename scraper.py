import yt_dlp
import numpy as np
import os
import sys
from datetime import datetime, timedelta
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
    now_iso = datetime.now().isoformat()
    
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
                
            views_list = [e.get('view_count', 0) for e in entries if e.get('view_count')]
            median_views = float(np.median(views_list)) if views_list else 1000.0

            for e in entries:
                vid = e.get('id')
                if not vid:
                    continue
                    
                views = int(e.get('view_count') or 0)
                duration = int(e.get('duration') or 0)
                outlier_score = round(views / median_views, 2) if median_views > 0 else 1.0
                
                doc_ref = db.collection('trend_videos').document(vid)
                doc_snap = doc_ref.get()
                
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
                    'baselineViews': median_views,
                    'outlierScore': outlier_score,
                    'lastUpdated': now_iso
                }
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
