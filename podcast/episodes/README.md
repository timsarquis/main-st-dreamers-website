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

Dates are stored as timezone-aware ISO timestamps and displayed in America/Los_Angeles. Episode schema includes only source-supported metadata. The sitemap preserves all pre-existing URLs and adds one canonical per episode. It omits lastmod because a publication date does not establish when later transcript/description changes happened. Related cards use deterministic weighted TF-IDF cosine similarity and link to their local pages; see discovery details below.

The main podcast list is static RSS detail links, using its existing episode-row styling. `data-static-details` prevents the Spotify JavaScript from replacing them with play buttons. The existing homepage/player Spotify refresh remains separate and best-effort; it cannot determine or remove the RSS archive. Apple links in the About block are clearly show links. Spotify episode links come from an exact-title match in the existing Spotify snapshot or an episode ID explicitly present in the feed's Spotify transcript URL; otherwise the verified RSS source link is used.

## GitHub Actions and deployment

`.github/workflows/refresh-episodes.yml` extends the existing Pages deployment workflow rather than introducing a competing deployment. Schedule: `17,47 * * * *` (twice hourly, in UTC). Also runs on pushes to main and manual `workflow_dispatch`. GitHub schedules are best-effort and may be delayed.

The workflow runs tests, preserves the existing Spotify player refresh, synchronizes RSS, validates SEO, then commits only generated website outputs using “Sync Dreaming of Disney podcast episodes”. A commit made with the normal GITHUB_TOKEN does not retrigger push workflows, preventing loops. The same job explicitly deploys via the existing Pages artifact pipeline, so it does not depend on that suppressed push event. No-op scheduled/manual runs skip both commit and deployment; code pushes still deploy. The existing `podcast-pages` concurrency group serializes this workflow. A failed git push aborts before deployment, rather than deploying changes that were not saved. Branch rules/environment protection can require repository configuration by the owner; no personal access token is used.

Manual run: GitHub repository → Actions → **Sync Dreaming of Disney podcast episodes** → **Run workflow** → main. The repository must allow GitHub Actions write access (`contents: write`); existing Pages permissions and environment are retained. No additional secrets are required.


## Archive search and related episodes

`assets/js/podcast-search.mjs` adds a labeled search field to the existing archive rows; `assets/css/podcast-search.css` is archive-only. The pure matching helpers are `assets/js/podcast-search-core.mjs`. The search index is `assets/data/podcast-search-index.json`, generated by the same RSS sync. It contains GUID, original title, episode number, slug, relative detail URL, ISO publication date, normalized description, and sorted unique transcript terms. At 143 episodes it is approximately 435 KB, versus over 2 MB for the source cache. Transcript repetition, timestamps, artwork, and unrelated metadata are omitted. Transcript term matching does not imply that a multiword phrase was spoken contiguously; title/description phrase matching uses actual word order.

No search-index request occurs on normal page load. Focus or a nonempty `q` parameter triggers lazy loading. Input is debounced by 150 ms and stale request results are ignored. A failed index request restores the normal archive with an explanatory message and can be retried. Clearing restores the original static list. Without JavaScript the entire archive remains ordinary HTML links and the inactive search control is hidden.

Search normalizes case, accents, apostrophes, punctuation, whitespace, and Fast Pass/FastPass. Each matched query term contributes 100 coverage points, with per-field additions of title 10, description 4, transcript 1; full title phrases add 40 and description phrases add 12. Exact single episode-number queries add 30. Partial terms are accepted; transcript terms use prefix matching. Equal scores resolve by publication date then GUID. Result counts are announced through a separate polite live region. `?q=` supports shared/bookmarked searches and browser back/forward; URL changes use history.pushState without reloading. The index never replaces the crawlable archive in the original HTML.

`scripts/podcast_discovery.py` computes related episodes at build time. It uses meaningful unigram/bigram TF-IDF vectors, logarithmically saturated frequencies, and cosine similarity. Title, description, and transcript fields are normalized separately before weighting 5:3:1, so long transcripts cannot dominate. Simple plural/possessive normalization and Fast Pass spelling normalization improve overlap. Common English words and show/promotional boilerplate (Disney, Disneyland, episode, podcast, Tim, Audreyann, social/shop language) are excluded. Generic editorial terms such as history, recap, studios, trip, and news are down-weighted to 15% as standalone terms; useful compound phrases retain their weight. Vocabulary appearing in at least 70% of an archive with 10+ records is excluded. Specific topic terms such as Pixar, FastPass, Lightning Lane, Club 33, Matterhorn, EPCOT, and Halloween remain available.

Every episode receives the top three non-self, distinct positive-score matches. Ties resolve by publication date descending, then GUID. If there is no meaningful signal for enough candidates, nearby publication-order episodes fill the remaining slots. Missing transcripts use titles and descriptions. Relationships are recalculated for the entire archive on each sync, including when a transcript arrives or changes. Cards are rendered directly into static HTML after the transcript and before About, using the approved card design. No external search service, AI API, or ML dependency is used.

The workflow additionally stages the generated search index; its schedule, RSS fetching, and Pages deployment remain unchanged. Search tests use `node --test tests/podcast_search.test.mjs`; discovery and RSS tests use the existing Python unittest command. Stable generated bytes are still written only when changed.

### Verified related selections

| Test episode | Three related episodes | Why the lexical matches fit |
| --- | --- | --- |
| Keep It, Change It or Tear It Down: Fixing Disneyland (newest, transcript available) | Why does [insert Disney ride here] always break down?; Under and Overrated rides at Disney Parks!; D23 Recap: Tomorrowland Is FINALLY Getting Some Love! | Attraction changes, ride opinions, and Tomorrowland overlap in the source text. |
| Inside Disneyland’s Club 33 (older, transcript available) | Would you rather...?; Disney Trivia Showdown: Who Knows the Parks Best?; What if Walt Disney lived? | The first two mention Club 33; the third shares Walt/history vocabulary with the Club 33 transcript. |
| The complete history of Disneyland's FastPass system! (older, no transcript) | Lightning Lane Premiere Pass & Our top 3 tips!; All things Genie Plus!; Genie+ is dead! | FastPass/Lightning Lane/Genie terminology connects queue systems using titles and descriptions alone. |
| Inside Pixar Studios! Secret Rooms, Movie Magic & Disney Hot Takes (specific topic, transcript available) | Unpopular Disney opinions!; If you only had one day...; Toy Story 5 Surprised Us (And Called Out Every Parent) | The first two overlap with the hot-takes part of the episode; Toy Story 5 shares Pixar/movie vocabulary. |

Validation: all seven requested topic searches, mixed capitalization, partial terms, punctuation, numeric episode lookup, empty/no-result searches, clearing, shared q URLs, and browser history passed. Browser inspection at 1440/768/390 px found no horizontal overflow or JavaScript exceptions. A reduced mobile viewport height after focusing the input also passed; this simulates keyboard space but is not a physical iPhone keyboard test. No search index is requested on the initial archive load, and all 143 links remain with JavaScript disabled. All pages contain three distinct non-self related cards as static HTML. Existing slugs, canonicals, titles, dates, descriptions, and transcript wording were checked against the prior cache. RSS synchronization was run twice against the live feed: the second unchanged run returned zero changed files. Four JavaScript tests and ten Python tests pass, and actionlint validates the workflow.
