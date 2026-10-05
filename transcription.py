"""Explicit owner-supplied WAV excerpt fallback; never downloads YouTube audio."""
import base64
import hashlib
import io
import math
import re
import wave
from datetime import datetime, timezone

from content_policy import excluded
from research import PROJECT, VIDEO_ID

MODEL = 'gemini-3.5-transcribe'
MAX_BYTES = 8 * 1024 * 1024


def wav_duration(audio):
    if not audio or len(audio) > MAX_BYTES:
        raise ValueError('Upload a PCM WAV excerpt of at most 8 MiB')
    try:
        with wave.open(io.BytesIO(audio), 'rb') as wav:
            duration = wav.getnframes() / wav.getframerate()
            expected = wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
            if len(wav.readframes(wav.getnframes())) != expected:
                raise ValueError('Incomplete WAV audio')
    except (wave.Error, EOFError, ZeroDivisionError):
        raise ValueError('Use an uncompressed PCM WAV file') from None
    if not 0 < duration <= 900:
        raise ValueError('Timestamped audio excerpts must be no longer than 15 minutes')
    return duration


def parse_words(payload, duration):
    candidates=payload.get('candidates') or []
    if not candidates or candidates[0].get('finishReason') != 'STOP':
        raise ValueError('Transcription did not complete')
    words=[]
    for part in candidates[0].get('content',{}).get('parts',[]):
        for word in part.get('audioTranscription',{}).get('words',[]):
            offsets=[]
            for key in ('startOffset','endOffset'):
                raw=word.get(key)
                if not isinstance(raw,str) or not re.fullmatch(r'\d+(?:\.\d+)?s',raw):
                    raise ValueError('Transcription is missing valid word timestamps')
                offsets.append(float(raw[:-1]))
            start,end=offsets
            if not 0 <= start <= end <= duration + 1 or not isinstance(word.get('word'),str):
                raise ValueError('Invalid word timing')
            if words and start < words[-1]['start']:
                raise ValueError('Word timestamps are out of order')
            words.append({'text':word['word'],'start':start,'end':end})
    if not words:
        raise ValueError('No timestamped speech returned; no findings will be invented')
    segments=[]
    size=0
    for i in range(0,len(words),20):
        chunk=words[i:i+20]
        text=' '.join(w['text'] for w in chunk)
        if size+len(text)>24000: break
        segments.append({'id':len(segments),'text':text,'start':chunk[0]['start'],'end':chunk[-1]['end']})
        size+=len(text)
    return segments


def transcribe_wav(audio, session=None):
    duration=wav_duration(audio)
    if session is None:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        credentials,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        session=AuthorizedSession(credentials)
    url=f'https://aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/global/publishers/google/models/{MODEL}:generateContent'
    response=session.post(url,json={
        'contents':[{'role':'user','parts':[{'inlineData':{'mimeType':'audio/wav','data':base64.b64encode(audio).decode('ascii')}}]}],
        'generationConfig':{'audioTranscriptionConfig':{'mode':'VERBATIM','wordTimestamp':True}}
    },timeout=120)
    if response.status_code!=200:
        raise RuntimeError(f'Transcription failed (HTTP {response.status_code}); no automatic retry')
    payload=response.json()
    return {'segments':parse_words(payload,duration),'source':'owner_uploaded_audio',
            'language':'automatic_detection','scope':f'Owner-linked audio excerpt ({duration:.1f} seconds); first 24,000 transcript characters. Video identity is owner-confirmed, not independently verified.',
            'model':MODEL,'capturedAt':datetime.now(timezone.utc).isoformat(),'usage':payload.get('usageMetadata',{})}


def store_uploaded_transcript(db,body,transcriber=transcribe_wav):
    if not isinstance(body,dict) or body.get('confirmedSource') is not True:
        raise ValueError('Confirm permission to process this audio and the linked source video')
    video_id=body.get('videoId')
    if not isinstance(video_id,str) or not VIDEO_ID.fullmatch(video_id):
        raise ValueError('Select a valid radar video')
    offset=body.get('startSeconds',0)
    if not isinstance(offset,(int,float)) or not math.isfinite(offset) or not 0 <= offset <= 86400:
        raise ValueError('Provide the excerpt start time in seconds')
    video=db.collection('trend_videos').document(video_id).get()
    if not video.exists or excluded(video.to_dict()):
        raise ValueError('Video is unavailable or excluded from research')
    encoded=body.get('audioBase64')
    if not isinstance(encoded,str) or len(encoded)>12*1024*1024:
        raise ValueError('Audio upload too large')
    try: audio=base64.b64decode(encoded,validate=True)
    except (ValueError,TypeError): raise ValueError('Invalid audio encoding') from None
    wav_duration(audio)
    fingerprint=hashlib.sha256(audio).hexdigest()
    ref=db.collection('research_transcripts').document(video_id)
    snapshot=ref.get()
    old=snapshot.to_dict() if snapshot.exists else None
    if old and old.get('audioHash')==fingerprint and old.get('startSeconds')==offset and old.get('model')==MODEL:
        return {'videoId':video_id,'status':'transcribed','cached':True,'segments':len(old['segments'])}
    if old and body.get('replaceTranscript') is not True:
        raise ValueError('A transcript already exists; explicitly approve replacement')
    transcript=transcriber(audio)
    for segment in transcript['segments']:
        segment['start']+=offset
        segment['end']+=offset
    transcript.update(audioHash=fingerprint,startSeconds=offset)
    if old:
        old_hash=hashlib.sha256(repr(old).encode()).hexdigest()
        ref.collection('revisions').document(old_hash).set(old)
    ref.set(transcript)
    return {'videoId':video_id,'status':'transcribed','cached':False,'segments':len(transcript['segments'])}
