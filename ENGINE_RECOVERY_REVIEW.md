# MinoMasal uçtan uca kurtarma — 13 Kasım 2026

## Release decision

**BLOCKED / NOT READY FOR PUBLICATION.** This PR does not merge PR #4 and does
not enable automatic publication. It selectively reuses tested image-provider
and compositor code without copying historical generated images/rejected assets.
Main, secrets, existing ledger, #45/#46 skips, the 10 November skip, canonical
Tonton JSON/reference and existing lock implementation are unchanged.

## Evidence and audit

- Main was `af05a9c`. PR #4 was open/draft at `3d6f6b1`.
- The 13 November daily run `43459456042` started at 16:07:11 UTC / 19:07:11 TR;
  it produced a review packet and skipped actual video generation and publishing.
  A green run was not a published video.
- The last failed daily run `43255161835` installed dependencies, generated 68
  and then 67 narration words and received HTTP 402 on the third **Pollinations
  text** request. No image, voice, MP4 or upload followed.
- GitHub workflow metadata: 52 registered workflows; Facebook daily/publish,
  video preview and legacy daily public YouTube workflows were disabled manually.
  No workflow state was changed by this task. Repository Actions-variable and
  secret-list administration is HTTP 403 for the integration; runtime presence
  and access are therefore checked in a read-only manual test using Secrets.
- The static inventory parses all 54 workflow files and all 84 root Python
  modules in this branch without importing/executing arbitrary modules. The
  inventory identifies events, permissions, concurrency and action pinning.
- Initial full offline suite: **220 passed**. Full local FFmpeg diagnostic passed
  actual 1080×1920, H.264/yuv420p, AAC/48k/stereo, full decode, stream synchronization,
  subtitle timeline, audio levels and black-frame checks. Its temporary synthetic
  video was deleted and is explicitly **not a Tonton MP4**.

## Final architecture and behavior

1. `minomasal_story_sources.py`: #47 always reads the user-requested existing
   89-word / ten-scene Tonton story, unchanged. `story_queue/catalog.json` binds
   approval to its hash and topic. The withdrawn fox draft is never selected.
   Other stories may use only allowlisted Gemini text on an owner-attested free
   account, then fall back only to an approved hash-bound local queue entry.
   An empty queue stops; a story number is never skipped to find easier content.
   Local word/scene/cast/name/object/language/repetition checks run before render.
   Semantic originality, child suitability and pixels remain human review tasks.
2. `minomasal_publish_engine.py`: compose only approved genuine RGBA sprites and
   approved backgrounds. #47 requires one Tonton, canonical reference binding,
   loaded/unloading/empty cargo assets and the bridge timeline. Empty catalogue,
   missing scene plan or missing hash-bound human scene review stops before TTS.
   No picture API is silently substituted; no synthetic fixture enters production.
3. The existing `aligned_scene_voices`, Sami model/voice, renderer, music, subtitle
   style and channel settings are retained. Real TTS probing and rendering require
   `MINOMASAL_GEMINI_FREE_TIER_CONFIRMED=true` set by the owner **only after checking
   the actual project and available quota**. A model catalogue is not this proof.
4. `minomasal_engine_qa.py` enforces 1080×1920, H.264/yuv420p, AAC, 3–180 seconds,
   valid FPS, synchronized stream durations/start times, full FFmpeg decode,
   audible/unclipped signal, no extended black gaps and valid subtitle timing.
   Machine checks cannot approve character identity, action, logos or natural speech.
5. Daily cron remains `7 16 * * *`, with the same shared concurrency and read-only
   daily lock preflight. The preparation job now has **contents: read**, no social
   media credentials, no reservation/upload calls and no Pollinations key. It
   uploads reports and a real MP4 only if one exists. Blocked production exits
   nonzero and emits an Actions failure annotation/summary; no email/Slack service
   is added. GitHub's own notification delivery depends on repository/user settings.
6. The manual workflow downloads an existing successful **main** preparation
   artifact, verifies source commit ancestry, exact user-approved video SHA256,
   canonical story identity, asset receipt and quality. Only a separate explicit
   manual job receives write permission and upload secrets. Live scope/account/
   complete-history checks precede atomic daily reservation. No regeneration
   happens during approval/publication.
7. The existing dual publisher persists `ambiguous` before each irreversible
   platform request, stores accepted IDs before verification, and marks published
   only after YouTube processing/public status or Instagram permalink/type is
   verified. Stored public URLs remain in the existing ledger structure. A
   successful platform is skipped on partial retry. Explicit same-day resume
   requires the identical video hash and exactly one published/one pending
   platform, uses lock SHA compare-and-swap and preserves prior lock ownership.
   Ambiguous/error states never reset automatically. No existing lock was edited.

## Allowed providers and cost controls

| Purpose | Allowed | Default / blocking condition |
|---|---|---|
| #47 text | Existing canonical local JSON | No inference, no Pollinations dependency |
| Future text | Gemini `gemini-3.8-flash`, approved local queue | Free-account attestation required before Gemini; no paid fallback |
| Production images | Approved local layered composition | Missing real assets or review blocks; no generative fallback |
| Cloudflare verification | FLUX model search, subscriptions, account-wide usage | Separate production/audit tokens; no image requests in this task |
| Narration | Existing `gemini-3.8-flash-tts`, Sami | Same free-account requirement; no automatic voice change or cloning |
| Publishing | Existing YouTube/Instagram/hosting endpoints | Exact-file manual approval, scopes, history, lock and receipts required |

HTTP 400/402/403 are not blindly retried. Text 429/temporary 5xx have at most
three attempts with 1/2-second waits; inference network timeouts do not replay.
Instagram upload POSTs have no automatic replay; safe metadata GETs are bounded.
The original daily dependencies are preserved; engine installs use a Python 3.11
lock file with exact versions and package hashes, an 8-minute pip cap, bounded
APT and pinned Node.js 24 actions on Ubuntu 24.04.

## Voice fallback research

Google's current official pricing documents free input/output for Gemini 3.8
Flash TTS **on the Free tier**; paid-tier pricing is separate. Account tier and
remaining quota are not inferable from model-list access. No subscription,
payment, billing permission or plan upgrade is performed here.

The current Turkish Piper `tr_TR/dfki/medium` model card points to DFKI data under
**CC BY-NC-SA 4.0**. It is not a commercially cleared automatic fallback and was
not downloaded/integrated. Earlier Turkish voices removed at contributors'
request are not resurrected. No licensed and quality-verified replacement has
yet been approved. Fallback speech remains blocked rather than changing voices.

Official references:
- https://ai.google.dev/gemini-api/docs/pricing#gemini-3.8-flash-tts
- https://ai.google.dev/gemini-api/docs/speech-generation
- https://huggingface.co/rhasspy/piper-voices/blob/main/tr/tr_TR/dfki/medium/MODEL_CARD
- https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/
- https://developers.cloudflare.com/workers-ai/platform/pricing/
- https://developers.google.com/youtube/v3/docs/channels/list
- https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/content-publishing/

## Acceptance still missing

- `visual_assets/catalog.json` is still empty. Complete Tonton poses, correct
  construction-site scenes and actual human approvals are missing. The original
  reference is opaque/cropped and prior FLUX candidates are rejected; they are not
  made approved by this PR.
- YouTube upload/read and Instagram read/publish permissions must pass independently;
  read-only audit results are recorded in the new real-runner artifact. #47's
  absence is not declared independently verified if YouTube history is inaccessible.
- Actual Gemini Turkish synthesis is performed only if free account attestation
  is already present; otherwise the precise blocked reason is recorded. No test
  WAV, quota, listening result or real story MP4 is invented.
- A real 89-word Turkish Tonton MP4 with all reviewed story scenes does not yet
  exist. No video artifact link or final publication approval can be honestly
  supplied until these prerequisites pass. Diagnostic artifacts are not a video.
- Automatic publishing remains absent from the daily workflow. Enabling it
  requires separately documented explicit user approval **after** a real verified
  successful manual publication; this PR contains no switch that silently does so.

## Rollback

Nothing is deployed to main, so closing the draft PR rolls back this attempt.
If merged later, revert the merge/code commit through a separate reviewed PR
and restore the prior preparation hold. Never revert successful platform IDs,
remove skipped records, delete locks, erase artifacts or reset an ambiguous
upload to pending. Keep publication closed during rollback; reconcile any
external IDs against real APIs before a retry. Secrets are never part of rollback.
