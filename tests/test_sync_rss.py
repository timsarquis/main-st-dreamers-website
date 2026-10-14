import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sync_rss', ROOT / 'scripts/sync-rss.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def feed(title='A &amp; B', guid='one', description='&lt;p&gt;Hello&lt;/p&gt;', transcript=True):
    return f'''<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:podcast="https://podcastindex.org/namespace/1.0"><channel><item><guid>{guid}</guid><title>{title}</title><description>{description}</description><pubDate>Mon, 12 Oct 2026 05:12:00 GMT</pubDate><itunes:duration>01:04:55</itunes:duration><enclosure url="https://example.com/audio.mp3" type="audio/mpeg"/>{'<podcast:transcript url="https://example.com/transcript.srt" type="application/x-subrip"/>' if transcript else ''}</item></channel></rss>'''


class SynchronizationTests(unittest.TestCase):
    def test_stable_guid_slug_and_collision(self):
        first, _ = sync.parse_feed(feed(), {})
        changed, _ = sync.parse_feed(feed(title='Renamed'), {'one': first[0]})
        self.assertEqual(changed[0]['slug'], first[0]['slug'])
        another, _ = sync.parse_feed(feed(guid='two'), {'one': first[0]})
        self.assertNotEqual(another[0]['slug'], first[0]['slug'])

    def test_reject_empty_duplicates_entities(self):
        for source in ['<rss><channel/></rss>', feed().replace('</channel>', feed().split('<item>')[1].split('</item>')[0].join(['<item>', '</item>'])+'</channel>'), '<!DOCTYPE rss [<!ENTITY x "danger">]>'+feed()]:
            with self.assertRaises(ValueError): sync.parse_feed(source, {})

    def test_safe_notes_and_json(self):
        cleaned, _ = sync.notes('<p>Fine <strong>bold</strong><script>alert(1)</script><a href="javascript:evil()" onclick="evil()">link</a><img src=x onerror=evil()></p>')
        self.assertNotIn('script', cleaned)
        self.assertNotIn('alert', cleaned)
        self.assertNotIn('javascript:', cleaned)
        self.assertNotIn('onerror', cleaned)
        self.assertIn('<strong>bold</strong>', cleaned)
        self.assertEqual(json.loads(sync.json_script({'text': '</script>&'}))['text'], '</script>&')

    def test_transcript_wording_timestamps_and_voices(self):
        srt = '1\n00:00:01,000 --> 00:00:02,000\nHi &amp; welcome.\n\n2\n00:00:02,000 --> 00:00:03,000\nNext line.'
        turns = sync.parse_transcript(srt, 'application/x-subrip')
        self.assertEqual(turns[0]['text'], 'Hi & welcome. Next line.')
        self.assertIsNone(turns[0]['speaker'])
        self.assertEqual(turns[0]['timestamp'], '00:00:01.000')
        vtt = 'WEBVTT\n\n00:01.000 --> 00:02.000\n<v Tim>Hello</v>\n\n00:02.000 --> 00:03.000\n<v Audreyann>Hi</v>'
        turns = sync.parse_transcript(vtt, 'text/vtt')
        self.assertEqual([x['speaker'] for x in turns], ['Tim', 'Audreyann'])
        with self.assertRaises(ValueError): sync.parse_transcript('<html>Error</html>', 'text/plain')
        with self.assertRaises(ValueError): sync.parse_transcript('broken', 'application/x-subrip')

    def test_failure_retains_previous_transcript(self):
        episode, _ = sync.parse_feed(feed(), {})
        old = {'transcript': [{'text': 'Keep this', 'speaker': None, 'timestamp': None}], 'transcriptSource': {'url': 'https://example.com/transcript.srt'}, 'transcriptHash': 'old'}
        with patch.object(sync, 'fetch', side_effect=TimeoutError('offline')):
            result = sync.synchronize_transcript(episode[0], old)
        self.assertEqual(result['transcript'], old['transcript'])

    def test_second_run_and_transcript_later_update(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ['templates/episode.html', 'podcast/index.html', 'sitemap.xml', 'assets/data/spotify-episodes.json']:
                path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text((ROOT/relative).read_text())
            source = root/'feed.xml'; source.write_text(feed(transcript=False))
            sync.run(root, source)
            self.assertEqual(sync.run(root, source), 0)
            saved = json.loads((root/'assets/data/rss-episodes.json').read_text())['episodes'][0]
            slug = saved['slug']
            source.write_text(feed(title='New title'))
            with patch.object(sync, 'fetch', return_value='1\n00:00:01,000 --> 00:00:02,000\nActual text.'):
                self.assertGreater(sync.run(root, source), 0)
                self.assertEqual(sync.run(root, source), 0)
            page = (root/'podcast/episodes'/slug/'index.html').read_text()
            self.assertIn('Actual text.', page)
            self.assertIn('<details', page)
            self.assertIn('New title', page)
            source.write_text('<rss><channel/></rss>')
            before = (root/'assets/data/rss-episodes.json').read_bytes()
            with self.assertRaises(ValueError): sync.run(root, source)
            self.assertEqual(before, (root/'assets/data/rss-episodes.json').read_bytes())


if __name__ == '__main__': unittest.main()
