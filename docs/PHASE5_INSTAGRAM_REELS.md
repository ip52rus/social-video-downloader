# Phase 5: Instagram single-video provider scope and evidence

## Agreed scope and decision

On 2026-10-16 the user approved the first implementation PR from main
`9148c81ccdf6b3d97c43b7ed20f23b5766925a50`, on a separate feature branch and checkout.
The decision is GO for an experimental anonymous provider of public individual Reels.
It is not acceptance of production reliability or permission to rebuild/restart the
running Compose stack. At that stage the PR had to remain draft pending a separate
merge decision.

The handoff reports previously completed Gates 1–3C. The available Gate 3C report
records one metadata-only extraction (`download=False, process=False`), with five video
entries in a `/p/` playlist, no downloaded media and no authentication. That establishes
only the reported metadata access/classification. Full Gates 1–3B reports were not
available in this implementation session; their detailed results are not reconstructed
or claimed as freshly verified. The user's explicit scope decision authorizes this
implementation without a new observation/waiting gate.

## PR 1 acceptance

These criteria record the original Reel-only PR. The approved current expansion is below.

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
  supplies the MP4 extension. Missing dimensions/codecs do not by themselves disqualify
  a direct MP4 candidate; explicit video/audio absence still does.
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
omit both dimensions and codecs on progressive MP4 data. Such direct candidates remain
eligible, with unknown codecs ranked below confirmed H.264/AAC; no streams or dimensions
are invented. Actual video/audio presence remains unverified until stream inspection.
Explicit audio-only/no-audio formats are rejected. A silently audio-free downloaded file
fails the existing transport helper safely; silent Reel support is not claimed or added here.
The provider does not transcode, add audio or duplicate the transport pipeline.

## Verification and follow-up

[TESTING.md](TESTING.md#experimental-instagram-reel-provider-2026-10-16) records offline
results, including real local yt-dlp processing and synthetic ffprobe preparation.
No real Instagram extraction/download or Telegram API request was run for this PR.
No dependency, Docker/Compose, default registry, handler or deployment changes are included.

PR #44 was subsequently merged. The first real provider smoke failed before acquisition:
13 returned formats, zero admitted, with incomplete video metadata in three formats;
the other ten rejection reasons were not verified. An offline regression using the
installed extractor's `video_versions` mapping confirmed and corrected the overly strict
dimension/codec evidence rule. This does not establish why every real format was rejected
or prove that the live Reel now downloads. See the follow-up evidence in TESTING.md.

PR #45 was subsequently merged. Its separately authorized repeat smoke on 2026-10-16
passed for one public Reel through the actual provider/service: 13 formats, 3 admitted,
10 rejected as manifest/fragment candidates, one extraction and one acquisition.
The actual file was MP4 H.264/AAC, 720x1280, 11.282041 seconds, 1,317,210 bytes;
preparation was passthrough, ffprobe and full FFmpeg decoding passed. There was no
Telegram upload. This resolves the observed admission failure for that case only.

## Approved expansion and current single-video-post stage

The user approved Reels, ordinary public single-video posts and future photo/video
carousels. This stage covers only `/p/<id>/` single-video posts, using the existing
provider and one-file `DownloadedMedia` contract. No second acquisition/preparation
pipeline, new dependencies or Telegram changes are introduced.

- Accept the same strict host allowlist and canonical HTTPS/www identity for `/reel/`
  and `/p/`; remove tracking queries/fragments without conflating the two path kinds.
- Decide content type from the extractor result, not the `/p/` path. Installed yt-dlp
  maps single-video products to video results; carousel products to playlists, including
  one-entry and mixed-media collections; photos have no admissible video formats and
  may raise an upstream no-video error. Test these mappings with synthetic responses.
- Reuse `_single_video()` to reject playlists, any `entries`, redirects, unclassified,
  inaccessible/private and DRM results before acquisition. Never recursively process
  entries or silently pick the first item. `noplaylist` is not a carousel-to-video conversion.
- Preserve direct HTTP(S) MP4 admission, manifest/fragment rejection, H.264/AAC priority,
  incomplete metadata support, bounded cache/snapshot reuse, safe filenames and cleanup.
- Expose only `VIDEO_WITH_AUDIO` / `DIRECT_DOWNLOAD`; no audio or quality menu. Reject
  unsupported modes and arbitrary quality IDs. Missing post titles use `Instagram Video`.
- Keep Instagram disabled in the default registry and leave Telegram handlers unchanged.

Real Reel smoke evidence predates this extension. Real `/p/` extraction/acquisition is
UNVERIFIED; offline tests do not establish current platform access or Telegram delivery.
Next: independent review and a separately authorized bounded real single-video-post smoke.
Telegram activation/deployment checks remain separately authorized work.

## Future carousel stage — not implemented

Photo/video carousels are approved future product scope, not supported downloads in this
stage. Deliver future carousel items as Telegram media groups in original order; split
more than 10 items into sequential groups, with no silent omission of unavailable elements.
The required multi-file acquisition/delivery design is deferred, not silently added to
the single-file provider. Photos and all collections continue to fail safely here.

Stories, private-content access, authentication, silent-video handling and additional
formats require separate scope decisions. Phase 5 and production reliability remain open.
