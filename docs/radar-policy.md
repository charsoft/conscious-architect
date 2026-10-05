# Radar content policy

The radar now uses reversible metadata-based triage. It does not claim to have
listened to, transcribed, or verified the content of each video.

## Controls

Firestore `trend_videos` fields:
- `radarOverride: "exclude"`: hide from research without deleting history.
- `radarOverride: "include"`: explicitly override automatic music classification.
- Delete the override field to return to automated triage.
- `radarExclusionReason` and `radarReviewedAt`: human review provenance.

The scraper merges metadata and deliberately leaves human overrides intact.
Automatic classification uses titles conservatively. Obvious sound baths,
binaural tracks and numbered-Hz tracks are likely music. Ambiguous talks about
music and guided practices remain available for review. This cannot reliably
measure the amount of speech; transcript/audio evidence is a future step.

The API filters exclusions before its 50-result limit, puts recently updated
records before stale records, and returns excluded IDs so curated entries do not
reintroduce them. A record older than seven days, or missing its update time, is
marked stale. Legacy timezone-free scraper timestamps are interpreted as UTC.
The UI prefers live metadata over curated duplicates and displays freshness,
format group and classification status.

The scraper excludes automatic music candidates and human exclusions from its
sampled baseline. `radar_scoring.py` compares the same channel, duration band,
age band and metadata content class only when at least five matching peers exist.
Sparse or missing metadata falls back to an explicitly unadjusted channel sample.
The 1,000-view baseline floor remains. These are coarse observational comparisons,
not causal performance estimates or verified interview/Shorts classifications.
Publication dates often are unavailable in flat scraping, so many scores will
remain unadjusted. Existing scores are not backfilled by this code change.

## Verification

```
python -B -m unittest discover -s tests -p "test_*.py" -v
node --test tests/script-handoff.test.cjs
```

## Research-to-script roadmap

Caption research and reviewed voice-guided drafting are implemented locally; see
`research-workflow.md` and `voice-drafting.md` for tested behavior and limitations.
The intended sequence is:

1. Acquire permitted transcripts with source IDs, timestamps and availability status.
   Missing captions must not be replaced by fabricated quotations or analysis.
2. Analyze only selected videos on demand; cache results by transcript hash and
   model/prompt version. Record costs and reject unsupported source claims.
3. Derive a draft voice guide from owner-approved scripts. Separate personal
   experiences, technical facts, metaphors and spiritual beliefs explicitly.
4. Offer source-attributed patterns and original hook/title options for approval.
   Do not present view count correlation as a causal claim about hook effectiveness.
5. Expand approved seven-beat outlines into narration with length targets,
   version history and research notes separated from spoken text. Never overwrite
   a manually edited script without confirmation.

The owner selected Gemini 3.8 Flash and Gemini 3.5 Transcribe and manages the $10/day
spend control on Google's side. Production deployment still requires approval.
