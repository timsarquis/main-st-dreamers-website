# Main St. Dreamers

Official website for Main St. Dreamers, home of the Dreaming of Disney Podcast, original park-inspired merchandise, and Park Scout.

## Architecture

The established Main St. Dreamers design, with HTML, shared `styles.css`, `script.js`, and `park-scout.js`. No package manager, build process, database, or server is required. Open `index.html` locally to preview.

Routes: homepage `/`, Podcast `/podcast/`, Shop `/shop/`, Park Scout `/park-scout/`, About `/about/`, and `404.html`. All normal links and assets use relative paths so the site works beneath the temporary GitHub Pages repository path as well as a future custom domain. The 404 page accounts for the repository prefix when hosted on github.io.

## Deployment

Use GitHub Desktop for repository creation, commits, publishing, and pushes. Commit website changes to `main`, then publish the public repository named `main-st-dreamers-website`.

On GitHub: Settings → Pages → Build and deployment → Deploy from a branch → main → / (root) → Save. GitHub Pages serves the repository directly; `.nojekyll` disables Jekyll processing. Get the actual temporary URL from Pages settings. Leave the custom domain blank.

## Future domain migration — not part of initial setup

`mainstdreamers.com` will eventually become the website’s custom domain. `shop.mainstdreamers.com` will eventually be the Printify storefront, and `mainstdreamers.com/shop` will eventually redirect to that storefront. For now the Shop route is a coming-soon page, with no redirect.

**DO NOT change domain, DNS, CNAME, Cloudflare, Shopify, or Printify settings without explicit instruction.**

No CNAME file is included. Domain routing and storefront changes are intentionally outside this initial deployment.

The original design is preserved here, including the Park Scout screenshots, setup animation, feature comparison, $9.99 annual price, and privacy page. Podcast and About routes reuse the homepage and scroll to their corresponding sections. The Spotify player uses a public episode JSON file. A scheduled GitHub Action refreshes it twice an hour from public Spotify show and embed metadata, then publishes the static site. No API credentials or runtime server are needed. If Spotify changes its page format, the refresh fails and keeps the last successful deployment; the displayed list remains usable. This metadata refresh is separate from building the website; all pages remain plain HTML, CSS, and JavaScript.
