"""Conservative metadata triage, not a claim to have listened to a video."""
import re
from datetime import datetime, timezone

POLICY_VERSION = 1
MUSIC = re.compile(r'\bsound bath\b|\bbinaural beats\b|\bdrone tones\b|\b(?:sleep|meditation|relaxing|ambient) music\b|\b\d{3,4}\s*hz\b', re.I)
DISCUSSION = re.compile(r'\b(?:explained|science of|how .* works|interview|talk about)\b', re.I)
PRACTICE = re.compile(r'\b(?:guided|sleep) meditation\b|\baffirmations\b|\bfrequency\b', re.I)


def classify(title):
    title = title or ''
    if MUSIC.search(title) and not DISCUSSION.search(title):
        return {'contentType': 'likely_music', 'autoExcluded': True,
                'classificationReason': 'Title indicates a sound bath, frequency track or music. Metadata-only inference.',
                'classificationVersion': POLICY_VERSION}
    if PRACTICE.search(title) or re.search(r'\bmusic\b', title, re.I):
        return {'contentType': 'needs_review', 'autoExcluded': False,
                'classificationReason': 'May contain teaching, spoken practice or music; review required.',
                'classificationVersion': POLICY_VERSION}
    return {'contentType': 'unverified_spoken', 'autoExcluded': False,
            'classificationReason': 'No music indicator found; spoken content not yet verified.',
            'classificationVersion': POLICY_VERSION}


def excluded(doc):
    # Explicit human choices take priority, including a deliberate inclusion.
    override = doc.get('radarOverride')
    if override in ('exclude', 'include'):
        return override == 'exclude'
    return classify(doc.get('title', '')).get('autoExcluded', False)


def annotate(doc, now=None):
    result = dict(doc)
    result.update(classify(doc.get('title', '')))
    now = now or datetime.now(timezone.utc)
    try:
        updated = datetime.fromisoformat(str(doc.get('lastUpdated', '')).replace('Z', '+00:00'))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        result['stale'] = (now - updated).total_seconds() > 7 * 86400
    except (ValueError, TypeError):
        result['stale'] = True
    duration = doc.get('durationSeconds') or 0
    result['formatGroup'] = 'unknown' if not duration else 'short' if duration <= 180 else 'long_form'
    result['scoreLabel'] = 'Views / sampled channel median; not a causal hook-performance measure'
    return result
