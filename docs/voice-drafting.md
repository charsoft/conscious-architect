# Voice-guided drafting v1

## Approved reference snapshot

On 2026-10-05 the owner approved the **newer seven-beat versions** of:
- You Are the Architect: Stop Living by Default
- What Generative AI Taught Me About Clarity

`config/voice-v1.json` snapshots those versions from the launch catalog, not the
obsolete four-act Firestore scripts. Voice examples provide style, not a license
to reuse their personal stories, statistics or factual assertions in other episodes.
The original stored scripts have not been migrated or rewritten.

The editorial rules in `drafting.py` emphasize direct, compassionate teacher/minister
language, one technical mirror, the human-limit caveat, a practical exercise and
conscious participation rather than total control. Technical fact, metaphor and
spiritual belief are kept distinct. These are generation instructions, not a
substitute for human fact-checking or a guarantee against all model errors.

To update voice references after owner approval, add a new snapshot/version and
point `VOICE_PATH` to it. Draft cache keys include the full reference content;
records retain voice version and hash, model, prompt version and research IDs.

## User flow

1. Optionally analyze 1–3 eligible radar videos. Missing or rate-limited captions
   are reported honestly; their titles are not treated as transcript evidence.
2. In Stage 2, choose **Suggest hooks & blueprints**. Receive three original
   title/hook/keyword/blueprint alternatives. No-source drafts are explicitly
   labeled editorial suggestions, not outlier-derived findings.
3. Expand and review an option, then apply it with confirmation. The previous
   local version is archived. Stage 3 remains unchanged.
4. Refine all beats, then choose **Approve beats & draft narration**. This creates
   a preview with seven spoken sections, separate production notes, actual word
   count, an approximate duration at 140 wpm, and review notes.
5. Apply reviewed narration with confirmation. The approved opening, supplied
   story and compassionate caveat are preserved. An absent story is a visible
   owner-story placeholder, never an invented personal anecdote.

Requests and failed generations never replace the current episode. Applying a
preview is refused if the episode or its text changed since generation began.
Scripts are drafts for editorial review, not guaranteed factual final products.

## Persistence and recovery

- `script_drafts/{hash}` caches complete generated options/narration and provenance.
- Before local replacement, `tca_revision_{episode}_{time}_{uuid}` saves title,
  beats, script and research IDs. Failure to archive aborts replacement.
- **Restore previous local version** restores the most recent backup for the active
  episode and archives the current state first. Browser storage clearing removes
  these local backups; cloud revision history is separate.
- `/api/save` now persists structured Stage 3 as well as the text export. A
  Firestore transaction archives the old episode under `video_ideations/{id}/revisions`
  before changed content is merged. No cloud history browser/restore UI exists yet.
- The verbatim non-AI formatter remains available and asks before overwriting.
- Per-section production notes are visible separately and excluded from teleprompter
  export. Source research is never automatically pasted into the spoken text.

## Verification and remaining work

```
python -B -m unittest discover -s tests -p "test_*.py" -v
node --test tests/script-handoff.test.cjs tests/draft-editor.test.cjs
```

Live Vertex calls validated three options and seven narration sections; the test
narration contained 1,080 spoken words (~7.7 minutes). No production episodes were
changed by that test. Unit/editor tests cover preservation, cancellation, stale
previews, missing stories, invalid source references, caching and local recovery.

Deployment and production-runtime smoke testing still require owner approval.
Audio transcription via `gemini-3.5-transcribe` is implemented behind a disabled
feature flag: the live GA-model check returned HTTP 404. Peer age/duration/content
scoring is implemented for sufficiently complete metadata and five or more peers;
legacy and sparse samples remain explicitly unadjusted. Importing the owner's
channel analytics remains pending. Google-side spend controls are owner-managed;
there is no custom app-level daily spend cap.
