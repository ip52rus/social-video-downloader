# Phase 5: first Instagram Reel provider PR

## Agreed scope and decision

On 2026-10-16 the user approved the first implementation PR from main
`9148c81ccdf6b3d97c43b7ed20f23b5766925a50`, on a separate feature branch and checkout.
The decision is GO for an experimental anonymous provider of public individual Reels.
It is not acceptance of production reliability or permission to rebuild/restart the
running Compose stack. The PR must remain draft, with no autonomous merge.

The handoff reports previously completed Gates 1–3C. The available Gate 3C report
records one metadata-only extraction (`download=False, process=False`), with five video
entries in a `/p/` playlist, no downloaded media and no authentication. That establishes
only the reported metadata access/classification. Full Gates 1–3B reports were not
available in this implementation session; their detailed results are not reconstructed
or claimed as freshly verified. The user's explicit scope decision authorizes this
implementation without a new observation/waiting gate.

## PR 1 acceptance

- Implement `MediaProvider` without changing its contract or the one-file `DownloadedMedia`.
- Admit only individual `/reel/<id>/` paths on instagram.com, www.instagram.com or
  m.instagram.com; canonicalize to HTTPS/www and drop tracking queries/fragments.
- Reject `/p/` posts, Stories, profiles, collections (even one entry), redirect results,
  private/auth-gated metadata, DRM and unclassifiable or unsupported formats before
  media acquisition. Never enumerate a playlist or select its first entry.
- Start with direct HTTP(S) MP4 formats only. No DASH/HLS assembly, cookies, credentials,
  persistent extractor cache, new dependencies or application retry loop.
- Validate the effective protocol before acquisition using yt-dlp's protocol helper;
  reject manifest/fragment formats even with missing protocol or a misleading MP4 label.
  Signed direct MP4 URLs without a filename extension remain eligible when the extractor
  supplies the MP4 extension and video evidence.
- Prefer metadata-confirmed H.264/AAC, then incomplete codec metadata without known
  incompatible codecs, then other admitted MP4 formats. Retain yt-dlp quality ordering
  within each class and select one format without acquisition-error fallback.
- Expose one normal video route and no selectable qualities. Reject audio-only,
  video-only and supplied quality IDs. Explicit injection into `DownloadService` must
  produce the existing `DIRECT_DOWNLOAD` plan without adding Telegram UI.
- Reuse fresh inspection data between planning and acquisition; expired data must be
  revalidated. Keep cache lifetime and size bounded.
- Return exactly one nonempty regular file in the caller's output directory. Clean the
  internal acquisition workspace on success/failure and reject symlinks/extra outputs.
  Keep source titles/IDs out of filesystem paths.
- Treat title/uploader/duration as optional extractor data. Unknown duration remains
  unknown; Telegram preparation/upload metadata use the existing ffprobe/FFmpeg helpers.
- Validate the contract, failure boundaries, service injection and transport preparation
  offline; run the existing suite, Ruff, diff and security review. Record results and
  remaining checks explicitly.

Only the `VIDEO_WITH_AUDIO` route is exposed. The installed Instagram extractor may
omit codecs on progressive MP4 data; positive video dimensions are accepted as video
evidence, and unspecified audio remains unverified until actual stream inspection.
Explicit no-audio formats are rejected. A silently audio-free downloaded file fails the
existing transport helper safely; silent Reel support is not claimed or added here.
The provider does not transcode, add audio or duplicate the transport pipeline.

## Verification and follow-up

[TESTING.md](TESTING.md#experimental-instagram-reel-provider-2026-10-16) records offline
results, including real local yt-dlp processing and synthetic ffprobe preparation.
No real Instagram extraction/download or Telegram API request was run for this PR.
No dependency, Docker/Compose, default registry, handler or deployment changes are included.

After PR 1 review, a separate PR should enable default registration and common Telegram
routing/messages, with no audio or quality menu. Scope real anonymous Reel acquisition
and Telegram playback checks explicitly; deployment changes require separate permission.
Any future `/p/`, carousel, Story, private-content, authentication, silent-video or
additional-format support requires a separate scope decision. Phase 5 and production
reliability remain open until their own acceptance checks are satisfied.
