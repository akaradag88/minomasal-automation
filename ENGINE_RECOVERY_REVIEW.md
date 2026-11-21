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

## Final verified results — code `43b240d`

[Real runner run 43492247195](https://github.com/akaradag88/minomasal-automation/actions/runs/43492247195)
completed successfully as a **test/diagnostic workflow**, not as story production.
Artifact: [`minomasal-engine-evidence-43492247195`](https://github.com/akaradag88/minomasal-automation/actions/runs/43492247195/artifacts/14071065049).

- **228/228 offline tests passed locally and on Ubuntu 24.04 / Python 3.11.**
  A separate local, network-disabled real receipt-copy / deleted-image publication
  rejection integration test also passed. It creates/deletes a temporary tiny
  diagnostic clip; it is not a story or publishable video.
- Real runner: system installation **39 s**, hash-checked pip installation **12 s**,
  offline suite **7 s** (unittest reports 5.677 s), real FFmpeg diagnostic **1 s**.
  The 8-minute pip cap is met. Dependency consistency checks passed.
- All remote actions across 54 workflow files are pinned to commit SHAs; artifact
  actions were upgraded to the already tested Node.js 24 v7 pin. No workflow state
  or schedule was enabled by this PR.
- The shared Sami helper and legacy voice path now both enforce the same free
  account gate, 90-second request limit and single SDK attempt. Old live voice
  test files are import-safe; they no longer trigger synthesis during discovery.
- Human scene review is bound to both frame hashes and the exact story number /
  narration fingerprint. Reviewed frames cannot approve a newly changed script.
  Approved queued text takes precedence over needless fresh inference.
- Instagram media read HTTP **200**; permission read HTTP **200**;
  `instagram_basic`, `instagram_content_publish`, `pages_read_engagement` and
  `pages_show_list` granted. No container or media-publish request was sent.
  Complete returned history has no candidate #47 title match; renamed manual
  uploads remain a known limit of title-only matching.
- YouTube token refresh HTTP **200**, upload scope present, read scope absent;
  channel read HTTP **403 insufficientPermissions**. #47 is selected by the
  unchanged ledger but its absence on YouTube is **not independently verified**.
- Cloudflare distinct-token, model, free-plan and usage preflight passed. On
  13 November UTC the API reported **0 / 10,000 Neurons used**, **10,000 remaining**;
  analytics may lag. **No new image inference** was made in this task.
- Gemini text and configured Sami TTS models are listed (HTTP **200**). Owner
  free-account attestation is **false**. **No real speech generation** or model
  text inference was made. Neither model availability nor Cloudflare quota proves
  Google project billing status. Existing canonical #47 input works entirely locally.
- Actual preparation result: **blocked**, with missing approved scene plan,
  genuine approved character assets, approved backgrounds and free Gemini account
  attestation. **Zero MP4 files in the artifact**, zero new voice requests, zero
  daily reservations, zero ledger writes, zero social uploads, no payment/upgrade.
- The artifact metadata inventory contains all **28** currently available records.
  The relevant old #47 revision artifact contains only three partial images and
  story/report JSON, **no MP4 or WAV/MP3**. It cannot supply a complete rescue video.

Sanitized machine evidence is in `docs/engine-recovery/runner-evidence.json`,
`artifact-inventory.json` and `old-47-artifact-summary.json`. No credential values,
credential hashes, account IDs or Authorization headers are included.

## Required owner actions (no secret values in chat)

1. Re-consent the **existing** YouTube OAuth client for `youtube.readonly` while
   retaining `youtube.upload`, then update only `YOUTUBE_REFRESH_TOKEN` in GitHub
   Secrets. The existing local helper/guide in `docs/recovery-next-steps.md` remains
   available. The assistant cannot grant additional OAuth scopes by refreshing an
   upload-only token.
2. Verify the **actual current Google AI Studio project** is Free tier with
   sufficient model quota. Only then set the non-secret repository variable
   `MINOMASAL_GEMINI_FREE_TIER_CONFIRMED=true` (Settings → Secrets and variables →
   Actions → Variables). Do not set it for a paid project, an unknown plan or an
   exhausted quota. Re-check/reset this attestation after changing the associated
   project/key. No secret value needs to be supplied to the assistant.
3. Supply/approve the complete Tonton assets and construction-site scenes described
   in `visual_assets/story-plans/README.md`, or explicitly choose a different visual
   design to be drafted and reviewed first. The cropped RGB identity reference and
   rejected FLUX candidates are not silently promoted to production assets.
4. After those prerequisites, the assistant can run real synthesis/rendering and
   deliver the complete MP4/quality report. Only **then** approve that exact video
   hash for manual publication. Automatic daily publication requires separate
   explicit approval after a real verified successful pilot; it remains closed.
