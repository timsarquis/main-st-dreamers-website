"""Publish episode links in HTML so they remain readable without JavaScript."""
from pathlib import Path
import html
import json
import re
ROOT = Path(__file__).resolve().parents[1]

def main():
    episodes = json.loads((ROOT / 'assets/data/spotify-episodes.json').read_text())['episodes']
    if not episodes:
        raise ValueError('Cannot publish an empty episode list')
    latest = episodes[0]
    items = []
    entities = []
    for e in episodes:
        if not re.fullmatch(r'[A-Za-z0-9]{22}', e['id']) or e['url'] != 'https://open.spotify.com/episode/' + e['id']:
            raise ValueError('Invalid public episode URL')
        title = html.escape(e['title'])
        date = html.escape(e['releaseDate'])
        items.append(f'<li><a class="spotify-episode-button" href="{e["url"]}" target="_blank" rel="noopener noreferrer"><span class="spotify-episode-play" aria-hidden="true">▶</span><span><span class="spotify-episode-name">{title}</span><span class="spotify-episode-meta"><time datetime="{date}">{date}</time> · {round(e["durationMs"]/60000)} min</span></span></a></li>')
        entities.append({'@type':'PodcastEpisode','name':e['title'],'url':e['url'],'datePublished':e['releaseDate'],'duration':f'PT{round(e["durationMs"]/1000)}S','partOfSeries':{'@id':'https://mainstdreamers.com/podcast/#series'}})
    schema = '<script type="application/ld+json" id="episode-schema">'+json.dumps({'@context':'https://schema.org','@graph':entities},ensure_ascii=False).replace('<','\\u003c')+'</script>'
    for file in ['index.html','podcast/index.html']:
        p = ROOT / file
        s = p.read_text()
        s = re.sub(r'(<ol[^>]*id="spotify-episode-list"[^>]*>).*?(</ol>)',lambda m:m[1]+''.join(items)+m[2],s,flags=re.S)
        s = re.sub(r'<script[^>]*id="episode-schema"[^>]*>.*?</script>\s*','',s,flags=re.S)
        s = s.replace('</head>',schema+'\n</head>')
        s = re.sub(r'data-preview-episode-id="[A-Za-z0-9]+"', 'data-preview-episode-id="'+latest['id']+'"', s)
        s = re.sub(r'(id="spotify-playing-title">).*?(</h3>)', lambda m: m[1]+html.escape(latest['title'])+m[2], s)
        s = re.sub(r'href="[^"]*" id="spotify-featured-link"', 'href="'+latest['url']+'" id="spotify-featured-link"', s)
        s = re.sub(r'(iframe[^>]*src="https://open.spotify.com/embed/episode/)[A-Za-z0-9]+', lambda m: m[1]+latest['id'], s)
        s = s.replace('Getting the latest episodes…','Recent episodes. Choose an episode below.')
        p.write_text(s)
    print(f'Rendered {len(episodes)} crawlable episodes on homepage and podcast page')

if __name__ == '__main__':
    main()
