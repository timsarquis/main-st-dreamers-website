# Main St. Dreamers

Official website for Main St. Dreamers, home of the Dreaming of Disney Podcast, original park-inspired merchandise, and Park Scout.

## Architecture

The established Main St. Dreamers design, with HTML, shared `styles.css`, `script.js`, and `park-scout.js`. No package manager, build process, database, or server is required. Open `index.html` locally to preview.

Routes: homepage `/`, Podcast `/podcast/`, Shop `/shop/`, Park Scout `/park-scout/`, About `/about/`, and `404.html`. All normal links and assets use relative paths so the site works beneath the temporary GitHub Pages repository path as well as a future custom domain. The 404 page accounts for the repository prefix when hosted on github.io.

## Deployment

Use GitHub Desktop for repository creation, commits, publishing, and pushes. Commit website changes to `main`, then publish the public repository named `main-st-dreamers-website`.

On GitHub: Settings → Pages → Build and deployment → Source → GitHub Actions. The Refresh podcast episodes workflow publishes the refreshed episode snapshot and website together. Do not enable branch publishing: it can overwrite fresh episode data with the checked-in snapshot. GitHub Pages serves the repository directly; `.nojekyll` disables Jekyll processing. Get the actual temporary URL from Pages settings. Leave the custom domain blank.

## Future domain migration — not part of initial setup

`mainstdreamers.com` will eventually become the website’s custom domain. `shop.mainstdreamers.com` will eventually be the Printify storefront, and `mainstdreamers.com/shop` will eventually redirect to that storefront. For now the Shop route is a coming-soon page, with no redirect.

**DO NOT change domain, DNS, CNAME, Cloudflare, Shopify, or Printify settings without explicit instruction.**

No CNAME file is included. Domain routing and storefront changes are intentionally outside this initial deployment.

The original design is preserved here, including the Park Scout screenshots, setup animation, feature comparison, $9.99 annual price, and privacy page. Podcast and About routes reuse the homepage and scroll to their corresponding sections. The Spotify player uses a public episode JSON file. A scheduled GitHub Action refreshes it twice an hour from public Spotify show and embed metadata, then publishes the static site. No API credentials or runtime server are needed. If Spotify changes its page format, the refresh fails and keeps the last successful deployment; the displayed list remains usable. This metadata refresh is separate from building the website; all pages remain plain HTML, CSS, and JavaScript.

## Production migration

Production canonical URLs use `https://mainstdreamers.com`. Relative navigation and assets also work under the temporary Pages project URL. When GitHub adds CNAME, the scheduled episode deployment preserves it. Domain migration is authorized for website routing only; preserve all email records, unrelated subdomains, nameservers, and registrar settings.

## Search and AI crawler support

Canonical production pages are listed in `sitemap.xml`; `robots.txt` allows crawling, including search and AI crawlers. This does not guarantee indexing or AI citations. Page-specific titles, descriptions, social previews, and JSON-LD describe the visible content. Podcast and About pages have distinct content; the legacy Park Scout HTML URL redirects to its canonical route. The shop route points to the storefront canonical URL and retains its existing redirect.

`python scripts/render-episodes.py` publishes the current episode snapshot as ordinary HTML links and PodcastEpisode data. It runs after every scheduled Spotify refresh. `python scripts/check-seo.py` checks sitemap routes, canonical URLs, headings, structured-data syntax, in-page links, episode HTML, robots, and 404 indexing controls. The workflow includes both crawler files and deploys on pushes to main. Do not add invented app ratings, availability, or episode descriptions. FAQ markup describes the visible FAQ; no Google FAQ rich result is promised.

The episode renderer also updates the initial featured title, link, preview ID, and iframe to the newest episode, so the initial player matches the current catalog before JavaScript loads.

## Automated RSS episode archive

The official RSS now powers all individual episode pages and the podcast detail archive. The approved markup lives in `templates/episode.html`; `scripts/sync-rss.py` renders pages, transcripts, metadata, related cards, and sitemap entries using Python's standard library. `assets/data/rss-episodes.json` preserves GUID identities, stable URLs, and the last valid transcript. The existing homepage Spotify player refresh remains separate and best-effort.

The existing `.github/workflows/refresh-episodes.yml` runs at minutes 17 and 47 each hour, on pushes to main, and manually. It commits only changed generated outputs and deploys through the existing Pages artifact workflow; no-op scheduled runs do neither. No account credentials or new secrets are needed. See [the archive documentation](podcast/episodes/README.md) for the feed audit, failure behavior, field contract, supported transcript formats, local commands, and manual workflow instructions.
