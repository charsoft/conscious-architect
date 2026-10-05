# Caption-backed research (local implementation; deployment pending)

## What is implemented

`POST /api/research` uses the existing studio authentication. Select 1–3 Firestore
videos; excluded videos are rejected. Publisher English captions are preferred
before automatic English captions. Research uses at most 24,000 caption characters;
this scope is shown to the user, not represented as a full-video analysis.

Gemini extracts hook, keyword, structure and audience-problem observations. Each
observation must contain an exact short quote from the indicated caption segment.
Validation rejects unmatched quotations and incomplete model responses. This
proves traceability of the quoted text, NOT the correctness of all model reasoning.
Automatic captions can contain errors; no inference about visual hooks or actual
retention is supported by this path.

The research drawer displays findings and source timestamps as text, not HTML.
Copy exports actual research results rather than the former canned synthesis.
Research alone does not modify the current beats or narration. Cohort adaptation
now opens reviewed voice-guided options; it never pastes research notes into speech.
See `voice-drafting.md` for the options → approved blueprint → narration workflow.

## Provider and data flow

- `RESEARCH_MODEL`: defaults to owner-selected `gemini-3.8-flash`.
- `AI_LOCATION`: defaults to `global`.
- `GCP_PROJECT_ID`: existing Conscious Architect project.
- Uses Vertex REST with Application Default Credentials and the existing runtime
  service account. No API key or new dependency is needed for this text path.
- No Google Search grounding, automatic audio download or background AI job.
- An explicit owner-uploaded audio transcription path exists but is disabled
  pending verification of the selected transcription model's project access.
- Owner manages Google-side spending controls; no custom daily budget limiter.

Firestore collections:
- `research_transcripts`: caption excerpts and capture/source metadata by video ID.
- `research_analyses`: analysis, model, prompt version, usage and creation time;
  keyed by video ID + caption content + model + prompt version hash.

Existing transcript excerpts are reused until explicitly invalidated. They do not
currently detect later caption edits automatically. Cache keys change when a
transcript is replaced. No automatic model retry is attempted. The current
single-process HTTP server serializes requests; multi-instance duplicate billing
is still possible on simultaneous cache misses and needs a distributed claim
before horizontal scaling.

## Missing captions and transcription

Missing captions produce `needs_transcript`; rate limiting produces `rate_limited`.
No transcript or findings are invented. No automatic audio fallback is attempted
on HTTP 429, and no rate-limit circumvention is implemented.

The owner selected `gemini-3.5-transcribe` for audio fallback. Vertex documentation,
the official notebook, and REST discovery also document a service-account path:
`generateContent` with `audioTranscriptionConfig`, VERBATIM mode and word timestamps.
`transcription.py` implements that path for explicit owner-confirmed PCM WAV
uploads (8 MiB / 15 minutes maximum), validates timestamps, applies an excerpt
offset, caches the audio hash and transcript, and archives replaced transcripts.
Audio bytes are sent inline to Google and are not persisted by this app. Uploaded
video identity is owner-confirmed, not independently verified.

The live request for the exact GA model returned HTTP 404 in this project. No
preview model or other model was substituted. `TRANSCRIPTION_ENABLED` defaults
to false; the UI and API keep this path disabled until model access is verified.
This does not block caption-based research or voice-guided editorial drafts.

## Checks performed

- A small synthetic Gemini 3.8 Flash request succeeded through Vertex using the
  operator's account. Production service-account execution is not yet verified.
- A real-video caption probe returned HTTP 429; no real-video analysis passed yet.
- Python tests use mocks; JavaScript regression tests parse all inline scripts.
- No commit, deployment, dependency installation or IAM change made for this stage.
- Live voice-guided options and narration requests passed using the approved newer
  seven-beat references and an in-memory test store; no saved episodes were changed.
