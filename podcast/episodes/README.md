# Automated episode archive

The approved prototype is now `templates/episode.html`, rendered by `scripts/sync-rss.py` with `assets/css/episode.css`. Edit the template for shared episode markup and approved About copy; edit the shared stylesheet for episode styles. Never hand-edit generated episode HTML.

## Run locally

From the repository root:

```sh
python3 scripts/sync-rss.py --audit
python3 scripts/sync-rss.py
python3 scripts/check-seo.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

`--audit` parses the feed and reports counts/problems without writes or transcript fetches. `--feed-file /path/to/feed.xml` uses a saved feed for reproducible checks; transcript resources are still fetched. The real feed is public and requires no credentials.

## Feed observed October 13, 2026

Official feed: https://anchor.fm/s/fecb83c0/podcast/rss

143 items; 31 SRT transcript references; 112 without transcripts. No duplicate GUIDs, malformed entries, or slug collisions. Oldest item is the March 2022 introduction. Episode 143 has publication time `2026-10-12T05:12:00Z`, displayed as October 11 in America/Los_Angeles. Some transcript references belong to historical episodes. None of the fetched SRT resources identifies speakers.

Items supply title, HTML description, GUID, publication date, Spotify for Creators source link, author, audio enclosure URL/type/length, iTunes summary, explicit status, duration, artwork, episode number, and episode type. No season field appeared in this response. Channel metadata supplies title, description, link, language, author, artwork, category, feed self-link, hub, and lastBuildDate. Channel lastBuildDate changes are intentionally not recorded as episode changes.

Spotify uses `<podcast:transcript url="…" type="application/x-subrip" />` with namespace `https://podcastindex.org/namespace/1.0`. The reader also accepts the HTTP namespace variant. SRT caption timestamps are present. Fetches follow the actual reference URL; they do not construct transcript URLs. SRT, WebVTT (including supplied voice labels), and plain text are supported. JSON/unknown types fail explicitly and preserve any prior valid transcript rather than guessing their structure. Other parsers can be added in `parse_transcript`.

A stale feed response was initially returned by the local network intermediary. A direct network fetch returned the full current feed. The synchronization requests `Cache-Control: no-cache`; it also retains absent saved episodes if a future response is stale or truncated.

## Identity, content, and failures

`assets/data/rss-episodes.json` is the GUID-indexed content cache, including stable slug, canonical URL, description HTML/plain text, date, number/season, duration, enclosure, artwork, source URL, episode type/explicit status, transcript references, parsed transcript, and transcript source/hash when available. Availability is determined by a nonempty `transcript` array. There is no per-run timestamp, so unchanged inputs do not create commits.

New slugs use normalized titles; collisions receive a GUID hash suffix. Existing GUIDs keep their assigned slugs even after title changes. Records missing from a later RSS response are retained, not deleted. Duplicate/missing GUIDs and empty/malformed feeds abort before writes. Other malformed individual items retain their saved record and log the issue.

All referenced transcripts are retried each run, including unchanged URLs, so later transcripts and revised content are discovered. A timeout, malformed transcript, unsupported format, or temporarily missing reference retains the last valid transcript. New episodes without one still receive a page with “Transcript not currently available.” Errors are logged with the GUID. Description and other metadata changes replace the existing page in place.

All pages are rendered and validated before file replacement; each changed file is replaced atomically. A failed sync in CI stops before commit and deployment. Files are never deleted by the synchronizer. The complete transcript stays in static HTML inside the approved native collapsed disclosure. Caption text is preserved in source order, grouped into readable passages of up to 12 cues; supplied speaker changes start a new passage. No speaker labels, summaries, tags, quotes, or transcript wording are invented. Topic chips remain an optional template component but are omitted because the RSS has no structured topics.

Show notes allow only safe paragraphs, lists, emphasis, line breaks, and HTTP(S) links; executable content and attributes are dropped. Transcript/title text is escaped. JSON-LD is serialized with script-safe escapes. No podcast audio is downloaded or committed. Artwork uses the feed item, then channel artwork, then the existing show cover. URLs and site navigation preserve nested relative paths and GitHub Pages project prefixes.

Dates are stored as timezone-aware ISO timestamps and displayed in America/Los_Angeles. Episode schema includes only source-supported metadata. The sitemap preserves all pre-existing URLs and adds one canonical per episode. It omits lastmod because a publication date does not establish when later transcript/description changes happened. Related cards use the three nearest episodes in reverse chronological order and link to their local pages.

The main podcast list is static RSS detail links, using its existing episode-row styling. `data-static-details` prevents the Spotify JavaScript from replacing them with play buttons. The existing homepage/player Spotify refresh remains separate and best-effort; it cannot determine or remove the RSS archive. Apple links in the About block are clearly show links. Spotify episode links come from an exact-title match in the existing Spotify snapshot or an episode ID explicitly present in the feed's Spotify transcript URL; otherwise the verified RSS source link is used.

## GitHub Actions and deployment

`.github/workflows/refresh-episodes.yml` extends the existing Pages deployment workflow rather than introducing a competing deployment. Schedule: `17,47 * * * *` (twice hourly, in UTC). Also runs on pushes to main and manual `workflow_dispatch`. GitHub schedules are best-effort and may be delayed.

The workflow runs tests, preserves the existing Spotify player refresh, synchronizes RSS, validates SEO, then commits only generated website outputs using “Sync Dreaming of Disney podcast episodes”. A commit made with the normal GITHUB_TOKEN does not retrigger push workflows, preventing loops. The same job explicitly deploys via the existing Pages artifact pipeline, so it does not depend on that suppressed push event. No-op scheduled/manual runs skip both commit and deployment; code pushes still deploy. The existing `podcast-pages` concurrency group serializes this workflow. A failed git push aborts before deployment, rather than deploying changes that were not saved. Branch rules/environment protection can require repository configuration by the owner; no personal access token is used.

Manual run: GitHub repository → Actions → **Sync Dreaming of Disney podcast episodes** → **Run workflow** → main. The repository must allow GitHub Actions write access (`contents: write`); existing Pages permissions and environment are retained. No additional secrets are required.
