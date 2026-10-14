"""Refresh public Spotify episode metadata; no credentials or media downloads."""
import concurrent.futures
import datetime
import html
import json
from pathlib import Path
import re
import urllib.request

SHOW = "0kGpjoeXh3ykY0ItzQsVod"
ROOT = Path(__file__).resolve().parents[1]

def read(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")

def episode(episode_id):
    page = read(f"https://open.spotify.com/embed/episode/{episode_id}")
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not match:
        raise ValueError("Spotify embed metadata unavailable")
    entity = json.loads(match.group(1))["props"]["pageProps"]["state"]["data"]["entity"]
    if entity.get("relatedEntityUri") != f"spotify:show:{SHOW}":
        raise ValueError("Episode does not belong to this podcast")
    return {"id": episode_id, "uri": f"spotify:episode:{episode_id}",
            "url": f"https://open.spotify.com/episode/{episode_id}",
            "title": entity["title"], "releaseDate": entity["releaseDate"]["isoString"][:10],
            "durationMs": entity.get("duration", 0), "hasVideo": entity.get("hasVideo", False)}

def main():
    page = read(f"https://open.spotify.com/show/{SHOW}")
    ids = list(dict.fromkeys(re.findall(r'href="/episode/([A-Za-z0-9]{22})"', page)))[:20]
    if not ids:
        raise ValueError("Spotify returned no episode links; keep the previous deployment")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        episodes = sorted(pool.map(episode, ids), key=lambda item: item["releaseDate"], reverse=True)
    data = {"episodes": episodes, "updatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(), "stale": False}
    target = ROOT / "assets/data/spotify-episodes.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        previous = json.loads(target.read_text())
        if previous.get("episodes") == episodes:
            print("Spotify episode snapshot unchanged")
            return
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"Updated {len(episodes)} published episodes")

if __name__ == "__main__":
    main()
