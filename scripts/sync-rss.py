"""Synchronize the official RSS into static pages. Python standard library only."""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import logging
from pathlib import Path
import re
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

# Also supports importing this script directly in the existing unit tests.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from podcast_discovery import related_indices, search_index

ROOT = Path(__file__).resolve().parents[1]
FEED = 'https://anchor.fm/s/fecb83c0/podcast/rss'
BASE = 'https://mainstdreamers.com'
ITUNES = '{http://www.itunes.com/dtds/podcast-1.0.dtd}'
PODCAST = '{https://podcastindex.org/namespace/1.0}'
LOG = logging.getLogger('rss')


def safe_url(value):
    value = (value or '').strip()
    p = urllib.parse.urlsplit(value)
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password:
        return ''
    if any(ord(c) < 32 for c in value):
        return ''
    return value


def fetch(url):
    if not safe_url(url):
        raise ValueError('Unsafe resource URL')
    request = urllib.request.Request(url, headers={'User-Agent': 'MainStDreamers-RSS/1.0', 'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(12_000_001)
        if len(raw) > 12_000_000:
            raise ValueError('Resource exceeds 12 MB limit')
        return raw.decode('utf-8-sig')


def fetch_feed():
    # Some feed/CDN edges ignore Cache-Control and keep an old item list.
    # The nonce changes the request URL only, never persisted episode data.
    separator = '&' if urllib.parse.urlsplit(FEED).query else '?'
    return fetch(FEED + separator + urllib.parse.urlencode({'_rss_sync': time.time_ns()}))


class ShowNotes(HTMLParser):
    """Keep safe editorial formatting; discard executable tags and attributes."""
    allowed = {'p', 'br', 'strong', 'em', 'b', 'i', 'ul', 'ol', 'li', 'a'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.text = []
        self.suppressed = 0
        self.stack = []
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'iframe', 'object'):
            self.suppressed += 1
        if self.suppressed:
            return
        if tag in self.allowed:
            attr = ''
            if tag == 'a':
                url = safe_url(dict(attrs).get('href'))
                if url:
                    attr = ' href="' + html.escape(url, quote=True) + '" rel="noopener noreferrer"'
            self.output.append('<' + tag + attr + '>')
            if tag != 'br':
                self.stack.append(tag)
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag != 'br':
            self.handle_endtag(tag)
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'iframe', 'object') and self.suppressed:
            self.suppressed -= 1
            return
        if self.suppressed:
            return
        if tag in self.stack:
            while self.stack:
                current = self.stack.pop()
                self.output.append('</' + current + '>')
                if current == tag:
                    break
        if tag in ('p', 'li'):
            self.text.append('\n')
    def handle_data(self, value):
        if not self.suppressed:
            self.output.append(html.escape(value))
            self.text.append(value)
    def finish(self):
        while self.stack:
            self.output.append('</' + self.stack.pop() + '>')
        return ''.join(self.output), ''.join(self.text).strip()


def notes(raw):
    parser = ShowNotes()
    parser.feed(raw or '')
    return parser.finish()


def duration_seconds(value):
    if not value:
        return None
    pieces = value.strip().split(':')
    if len(pieces) > 3 or not all(re.fullmatch(r'\d+(?:\.\d+)?', x) for x in pieces):
        raise ValueError('Malformed duration')
    seconds = 0
    for piece in pieces:
        seconds = seconds * 60 + float(piece)
    return round(seconds)


def slugify(title):
    ascii_title = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', ascii_title.lower()).strip('-') or 'episode'


def parse_feed(source, existing):
    if '<!DOCTYPE' in source.upper() or '<!ENTITY' in source.upper():
        raise ValueError('XML entities are not permitted')
    channel = ET.fromstring(source).find('channel')
    if channel is None or not channel.findall('item'):
        raise ValueError('Empty or malformed feed; preserving existing archive')
    episodes, seen, issues = [], set(), []
    used = {e['slug'] for e in existing.values()}
    channel_image = channel.find(ITUNES + 'image')
    fallback_image = safe_url(channel_image.get('href')) if channel_image is not None else ''
    for item in channel.findall('item'):
        guid = (item.findtext('guid') or '').strip()
        if not guid or guid in seen:
            raise ValueError('Missing or duplicate GUID: ' + guid)
        seen.add(guid)
        try:
            title = (item.findtext('title') or '').strip()
            if not title:
                raise ValueError('Missing title')
            published = parsedate_to_datetime(item.findtext('pubDate', ''))
            if published.tzinfo is None:
                raise ValueError('Publication timezone missing')
            published = published.astimezone(dt.timezone.utc).isoformat().replace('+00:00', 'Z')
            description, text = notes(item.findtext('description') or item.findtext(ITUNES + 'summary') or '')
            slug = existing.get(guid, {}).get('slug')
            if slug is None:
                slug = slugify(title)
                if slug in used:
                    slug += '-' + hashlib.sha256(guid.encode()).hexdigest()[:10]
                if slug in used:
                    raise ValueError('Slug collision')
                used.add(slug)
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
                raise ValueError('Unsafe saved slug')
            enclosure = item.find('enclosure')
            image = item.find(ITUNES + 'image')
            transcripts = []
            for element in item:
                if element.tag in (PODCAST + 'transcript', '{http://podcastindex.org/namespace/1.0}transcript'):
                    url = safe_url(element.get('url'))
                    if url:
                        transcripts.append({'url': url, 'type': element.get('type', ''), 'language': element.get('language')})
            episode = {'guid': guid, 'title': title, 'slug': slug, 'canonical': BASE + '/podcast/episodes/' + slug + '/',
                       'descriptionHtml': description, 'description': text, 'published': published,
                       'episodeNumber': item.findtext(ITUNES + 'episode'), 'seasonNumber': item.findtext(ITUNES + 'season'),
                       'durationSeconds': duration_seconds(item.findtext(ITUNES + 'duration')),
                       'audioUrl': safe_url(enclosure.get('url')) if enclosure is not None else '',
                       'audioType': enclosure.get('type', '') if enclosure is not None else '',
                       'artworkUrl': (safe_url(image.get('href')) if image is not None else '') or fallback_image or BASE + '/assets/brand/podcast-cover.jpg',
                       'sourceUrl': safe_url(item.findtext('link')), 'episodeType': item.findtext(ITUNES + 'episodeType'),
                       'explicit': item.findtext(ITUNES + 'explicit'), 'transcriptSources': transcripts}
            episodes.append(episode)
        except (ValueError, TypeError, OverflowError) as error:
            issues.append(guid + ': ' + str(error))
            LOG.error('Invalid RSS entry %s; retaining any existing record', issues[-1])
    if not episodes:
        raise ValueError('No valid RSS episodes')
    LOG.info('Feed audit: %d items, %d transcript references, %d without; %d malformed; no duplicate GUIDs',
             len(channel.findall('item')), sum(bool(e['transcriptSources']) for e in episodes),
             sum(not e['transcriptSources'] for e in episodes), len(issues))
    return episodes, issues


def caption_text(text):
    # WebVTT markup encodes styling, voices and karaoke timestamps, not spoken text.
    speaker = re.search(r'<v(?:\.[^ >]+)?\s+([^>]+)>', text)
    name = html.unescape(speaker[1].strip()) if speaker else None
    return html.unescape(re.sub(r'<[^>]+>', '', text)).replace('\n', ' ').strip(), name


def parse_transcript(source, mime):
    if not source.strip():
        raise ValueError('Empty transcript')
    mime = mime.split(';')[0].lower()
    if mime in ('application/x-subrip', 'text/srt', 'text/vtt') or source.lstrip().startswith('WEBVTT'):
        cues = []
        for block in re.split(r'\r?\n\s*\r?\n', source.strip()):
            lines = block.splitlines()
            timing = next((i for i, line in enumerate(lines) if '-->' in line), None)
            if timing is None:
                if block.startswith(('WEBVTT', 'NOTE', 'STYLE', 'REGION')):
                    continue
                raise ValueError('Malformed caption block')
            start = lines[timing].split('-->')[0].strip()
            if not re.fullmatch(r'(?:\d{2,}:)?\d{2}:\d{2}[.,]\d{3}', start):
                raise ValueError('Malformed caption timestamp')
            text, speaker = caption_text('\n'.join(lines[timing+1:]))
            if not text:
                raise ValueError('Empty caption text')
            cues.append({'timestamp': start.replace(',', '.'), 'text': text, 'speaker': speaker})
        if not cues:
            raise ValueError('No caption cues')
        turns = []
        for cue in cues:
            if not turns or turns[-1]['speaker'] != cue['speaker'] or turns[-1]['cueCount'] >= 12:
                turns.append({**cue, 'cueCount': 1})
            else:
                turns[-1]['text'] += ' ' + cue['text']
                turns[-1]['cueCount'] += 1
        return turns
    if mime == 'text/plain':
        if source.lstrip().lower().startswith(('<!doctype', '<html')):
            raise ValueError('HTML returned instead of transcript')
        return [{'text': x.strip(), 'speaker': None, 'timestamp': None} for x in re.split(r'\n\s*\n', source) if x.strip()]
    # Fail closed on unknown formats rather than guessing JSON field semantics.
    raise ValueError('Unsupported transcript type: ' + mime)


def synchronize_transcript(episode, old):
    previous = {k: old[k] for k in ('transcript', 'transcriptSource', 'transcriptHash') if k in old}
    for source in episode['transcriptSources']:
        try:
            raw = fetch(source['url'])
            return {**episode, 'transcript': parse_transcript(raw, source['type']), 'transcriptSource': source,
                    'transcriptHash': hashlib.sha256(raw.encode()).hexdigest()}
        except Exception as error:
            LOG.warning('Transcript unavailable for %s: %s', episode['guid'], error)
    # Keep a valid prior transcript during outages or temporary feed omissions.
    return {**episode, **previous}


def display_date(episode):
    date = dt.datetime.fromisoformat(episode['published'].replace('Z', '+00:00')).astimezone(ZoneInfo('America/Los_Angeles'))
    return date.strftime('%B ') + str(date.day) + date.strftime(', %Y')


def duration_label(seconds):
    if seconds is None:
        return ''
    hours, rem = divmod(seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return ' '.join(v for v in (f'{hours} hr' if hours else '', f'{minutes} min' if minutes else '', f'{seconds} sec' if seconds else '') if v)


def json_script(value):
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def render_page(episode, related, template):
    esc = html.escape
    title, canonical = episode['title'], episode['canonical']
    intro = episode['description'].split('\n')[0]
    schema = {'@context': 'https://schema.org', '@type': 'PodcastEpisode', '@id': canonical + '#episode',
              'name': title, 'url': canonical, 'datePublished': episode['published'],
              'partOfSeries': {'@type': 'PodcastSeries', '@id': BASE + '/podcast/#series', 'name': 'Dreaming of Disney',
                               'publisher': {'@type': 'Organization', 'name': 'Main St. Dreamers', 'url': BASE + '/'}}}
    for key, value in (('description', episode['description']), ('episodeNumber', episode['episodeNumber']),
                       ('image', episode['artworkUrl'])):
        if value:
            schema[key] = value
    if episode['durationSeconds'] is not None:
        schema['duration'] = 'PT' + str(episode['durationSeconds']) + 'S'
    if episode['audioUrl']:
        schema['associatedMedia'] = {'@type': 'AudioObject', 'contentUrl': episode['audioUrl']}
        if episode['audioType']:
            schema['associatedMedia']['encodingFormat'] = episode['audioType']
    if episode.get('spotifyUrl'):
        schema['sameAs'] = [episode['spotifyUrl']]
    head = f'<title>{esc(title)} | Dreaming of Disney</title><link rel="canonical" href="{canonical}">'
    for name, value in [('description', intro), ('og:title', title), ('og:description', intro), ('og:url', canonical),
                        ('og:type', 'website'), ('og:site_name', 'Main St. Dreamers'), ('og:image', episode['artworkUrl']), ('twitter:card', 'summary_large_image')]:
        if value:
            head += f'<meta {"property" if name.startswith("og:") else "name"}="{name}" content="{esc(value, quote=True)}">'
    head += '<link rel="stylesheet" href="../../../styles.css"><link rel="stylesheet" href="../../../assets/css/episode.css"><script src="../../../assets/js/navigation.js" defer></script><script type="application/ld+json">' + json_script(schema) + '</script>'
    listen_url = episode.get('spotifyUrl') or episode['sourceUrl'] or episode['audioUrl']
    label = 'Listen on Spotify ↗' if episode.get('spotifyUrl') else 'Listen to the episode ↗'
    cta = f'<a class="button button-primary" href="{esc(listen_url)}" target="_blank" rel="noopener noreferrer">{label}</a>' if listen_url else ''
    number = ' · Episode ' + esc(episode['episodeNumber']) if episode['episodeNumber'] else ''
    duration = ' · ' + duration_label(episode['durationSeconds']) if episode['durationSeconds'] is not None else ''
    hero = f'<p class="eyebrow blue">Dreaming of Disney Podcast{number}</p><p class="episode-meta"><time datetime="{episode["published"]}">{display_date(episode)}</time>{duration}</p><h1>{esc(title)}</h1>'
    if intro:
        hero += '<p class="episode-intro">' + esc(intro) + '</p>'
    hero += '<div class="episode-actions">' + cta + '<a class="underlined-link" href="#transcript">Jump to transcript ↓</a></div>'
    artwork = '<figure class="episode-art"><img src="' + esc(episode['artworkUrl']) + '" width="640" height="640" alt="Dreaming of Disney podcast cover"><figcaption>With Tim &amp; Audreyann</figcaption></figure>'
    # No inferred topics: this optional chip component is populated only by explicitly supplied data.
    topics = episode.get('topics', [])
    description = ('<ul class="episode-topics" aria-label="Episode topics">' + ''.join('<li>' + esc(t) + '</li>' for t in topics) + '</ul>') if topics else ''
    description += '<div class="episode-description">' + (episode['descriptionHtml'] or '<p>Episode description not currently available.</p>') + '</div>'
    listen = ''
    if episode['audioUrl']:
        listen = f'<section class="episode-listen" aria-labelledby="listen-title"><h2 id="listen-title">Listen to This Episode</h2><audio controls preload="none" aria-label="Listen to {esc(title)}"><source src="{esc(episode["audioUrl"])}" type="{esc(episode["audioType"])}">Your browser does not support audio playback.</audio><p><a class="underlined-link" href="{esc(episode["audioUrl"])}">Open the episode audio ↗</a></p></section>'
    transcript = '<section class="episode-transcript" id="transcript" aria-labelledby="transcript-title"><div class="episode-section-heading"><div><p class="eyebrow blue">Read along</p><h2 id="transcript-title">Full Transcript</h2></div>'
    if listen_url:
        transcript += f'<a class="underlined-link" href="{esc(listen_url)}" target="_blank" rel="noopener noreferrer">Listen to the episode ↗</a>'
    transcript += '</div>'
    if episode.get('transcript'):
        transcript += '<details class="transcript-disclosure"><summary><span class="transcript-open-label">Read full transcript</span><span class="transcript-close-label">Close transcript</span></summary><p class="transcript-notice">Transcript provided by the podcast publisher and may contain transcription errors. <a class="underlined-link" href="' + esc(episode['transcriptSource']['url']) + '">Download the original transcript ↗</a></p><div class="transcript-copy">'
        for turn in episode['transcript']:
            timestamp = '<span class="transcript-time">' + esc(turn['timestamp'].split('.')[0]) + '</span>' if turn.get('timestamp') else ''
            if turn.get('speaker'):
                transcript += '<div class="transcript-turn"><h3>' + esc(turn['speaker']) + timestamp + '</h3><p>' + esc(turn['text']) + '</p></div>'
            else:
                transcript += '<p class="transcript-passage">' + timestamp + esc(turn['text']) + '</p>'
        transcript += '</div></details>'
    else:
        transcript += '<p class="transcript-notice">Transcript not currently available.</p>'
    transcript += '</section>'
    cards = ''
    for e in related:
        cards += '<article class="episode-card"><p class="episode-meta"><time datetime="' + e['published'] + '">' + display_date(e) + '</time></p><h3><a href="../' + e['slug'] + '/">' + esc(e['title']) + '</a></h3><a class="underlined-link" href="../' + e['slug'] + '/">Read episode ↗</a></article>'
    values = {'head': head, 'hero': hero, 'artwork': artwork, 'description': description, 'listen': listen, 'transcript': transcript, 'related': cards, 'year': str(dt.datetime.now(ZoneInfo('America/Los_Angeles')).year)}
    return re.sub(r'\{\{(\w+)\}\}', lambda m: values[m[1]], template)


class ValidatePage(HTMLParser):
    def __init__(self):
        super().__init__(); self.h1 = 0; self.canonical = []; self.script = False; self.data = ''; self.ids = set(); self.fragments = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'h1': self.h1 += 1
        if tag == 'link' and a.get('rel') == 'canonical': self.canonical.append(a.get('href'))
        if a.get('id'): self.ids.add(a['id'])
        if tag == 'a' and a.get('href', '').startswith('#'): self.fragments.append(a['href'][1:])
        if tag == 'script' and a.get('type') == 'application/ld+json': self.script = True; self.data = ''
        for key in ('src', 'href'):
            if a.get(key) and urllib.parse.urlsplit(a[key]).scheme and not safe_url(a[key]):
                raise ValueError('Unsafe generated link')
    def handle_data(self, data):
        if self.script: self.data += data
    def handle_endtag(self, tag):
        if tag == 'script' and self.script: json.loads(self.data); self.script = False


def validate_page(source, canonical):
    parser = ValidatePage(); parser.feed(source)
    if parser.h1 != 1 or parser.canonical != [canonical] or any(f not in parser.ids for f in parser.fragments):
        raise ValueError('Generated page failed semantic validation')
    if '{{' in source:
        raise ValueError('Unresolved template fields')


def changed_write(path, content):
    if path.exists() and path.read_text() == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as file:
        file.write(content); temporary = Path(file.name)
    temporary.replace(path)
    return True


def run(root=ROOT, feed_file=None, audit=False):
    cache_path = root / 'assets/data/rss-episodes.json'
    cached = json.loads(cache_path.read_text()) if cache_path.exists() else {'episodes': []}
    existing = {e['guid']: e for e in cached['episodes']}
    episodes, issues = parse_feed(Path(feed_file).read_text() if feed_file else fetch_feed(), existing)
    if audit:
        return
    spotify = json.loads((root / 'assets/data/spotify-episodes.json').read_text())['episodes']
    matches = {e['title']: e['url'] for e in spotify}
    for e in episodes:
        if matches.get(e['title']):
            e['spotifyUrl'] = matches[e['title']]
        elif existing.get(e['guid'], {}).get('spotifyUrl'):
            e['spotifyUrl'] = existing[e['guid']]['spotifyUrl']
        else:
            for t in e['transcriptSources']:
                m = re.search(r'/0kGpjoeXh3ykY0ItzQsVod/([A-Za-z0-9]{22})/transcript\.', t['url'])
                if m:
                    e['spotifyUrl'] = 'https://open.spotify.com/episode/' + m[1]
                    break
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        updated = list(pool.map(lambda e: synchronize_transcript(e, existing.get(e['guid'], {})), episodes))
    # Retain records not in this response: RSS truncation is never treated as deletion.
    merged = dict(existing)
    merged.update({e['guid']: e for e in updated})
    all_episodes = sorted(merged.values(), key=lambda e: (e['published'], e['guid']), reverse=True)
    template = (root / 'templates/episode.html').read_text()
    writes = {}
    relationships = related_indices(all_episodes)
    for i, e in enumerate(all_episodes):
        related = relationships[i]
        page = render_page(e, [all_episodes[z] for z in related], template)
        validate_page(page, e['canonical'])
        writes[root / 'podcast/episodes' / e['slug'] / 'index.html'] = page
    archive_path = root / 'podcast/index.html'
    archive = archive_path.read_text()
    archive = re.sub(r'\s*<p><a class="underlined-link" href="episodes/[^\"]+/">Read (?:the latest|the prototype) episode page:.*?</a></p>', '', archive)
    archive = re.sub(r'<div class="spotify-podcast"(?![^>]*data-static-details)', '<div class="spotify-podcast" data-static-details="true"', archive)
    archive = archive.replace('<p>Start with the newest, or find one you missed.</p>', '<p>Start with the newest, or find one you missed.</p>')
    items = ''.join('<li><a class="spotify-episode-button" href="episodes/' + e['slug'] + '/"><span class="spotify-episode-play" aria-hidden="true">↗</span><span><span class="spotify-episode-name">' + html.escape(e['title']) + '</span><span class="spotify-episode-meta"><time datetime="' + e['published'] + '">' + display_date(e) + '</time>' + (' · ' + duration_label(e['durationSeconds']) if e['durationSeconds'] is not None else '') + '</span></span></a></li>' for e in all_episodes)
    archive, count = re.subn(r'(<ol[^>]*id="spotify-episode-list"[^>]*>).*?(</ol>)', lambda m: m[1]+items+m[2], archive, flags=re.S)
    if count != 1: raise ValueError('Podcast list target missing')
    # The existing featured player is preserved, while the detail archive is RSS driven.
    schemas = [{'@type': 'PodcastEpisode', 'name': e['title'], 'url': e['canonical'], 'datePublished': e['published'], 'partOfSeries': {'@id': BASE + '/podcast/#series'}} for e in all_episodes]
    archive = re.sub(r'(<script[^>]*id="episode-schema"[^>]*>).*?(</script>)', lambda m: m[1]+json_script({'@context': 'https://schema.org', '@graph': schemas})+m[2], archive, flags=re.S)
    writes[archive_path] = archive
    sitemap_path = root / 'sitemap.xml'
    sitemap = ET.fromstring(sitemap_path.read_text())
    namespace = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
    known = {node.findtext(namespace+'loc'): node for node in sitemap}
    for e in all_episodes:
        if e['canonical'] not in known:
            node = ET.SubElement(sitemap, namespace+'url')
            ET.SubElement(node, namespace+'loc').text = e['canonical']
            known[e['canonical']] = node
        # RSS publication is not a trustworthy modification timestamp. Omit lastmod.
    ET.register_namespace('', namespace[1:-1]); ET.indent(sitemap, space='  ')
    writes[sitemap_path] = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(sitemap, encoding='unicode') + '\n'
    writes[root / 'assets/data/podcast-search-index.json'] = json.dumps(search_index(all_episodes), ensure_ascii=False, separators=(',', ':')) + '\n'
    writes[cache_path] = json.dumps({'feedUrl': FEED, 'episodes': all_episodes}, ensure_ascii=False, indent=2) + '\n'
    # Validate the entire output set before any replacement; replace individual files atomically.
    changes = sum(changed_write(path, content) for path, content in writes.items())
    LOG.info('Archive: %d pages, %d usable transcripts, %d unavailable; %d changed files', len(all_episodes),
             sum(bool(e.get('transcript')) for e in all_episodes), sum(not e.get('transcript') for e in all_episodes), changes)
    return changes


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--feed-file', help='Use a saved RSS response for repeatable validation')
    parser.add_argument('--audit', action='store_true', help='Parse and report only; no writes or transcript downloads')
    args = parser.parse_args()
    run(feed_file=args.feed_file, audit=args.audit)
