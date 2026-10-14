import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('discovery', Path(__file__).resolve().parents[1]/'scripts/podcast_discovery.py')
discovery = importlib.util.module_from_spec(spec); spec.loader.exec_module(discovery)


def episode(guid, title='Disney', description='', transcript=None):
    return {'guid':guid,'slug':guid,'title':title,'description':description,'episodeNumber':None,
            'published':'2026-10-01T00:00:00Z','transcript':transcript or []}


class DiscoveryTests(unittest.TestCase):
    def test_compact_index_matches_transcript_without_copying_speech(self):
        e=episode('one',title='Club 33',transcript=[{'text':'Club 33 club 33 is fun.'}])
        index=discovery.search_index([e])['episodes'][0]
        self.assertEqual(index['transcriptTerms'],['33','club','fun','is'])
        self.assertNotIn('Club 33 club 33',str(index))
        self.assertEqual(index['url'],'episodes/one/')

    def test_topic_similarity_not_boilerplate_or_transcript_length(self):
        archive=[episode('source','Pixar animation tour','Exploring Pixar studios'),
                 episode('good','Pixar movies','Animation and movie art'),
                 episode('unrelated','Halloween snacks','Food and treats', [{'text':'pixar '*1000+'snacks '*1000}]),
                 episode('other','Park queues','Planning lines'),episode('blank')]
        choices=discovery.related_indices(archive)
        self.assertEqual(choices[0][0],1)
        self.assertEqual(len(choices[0]),3)
        self.assertNotIn(0,choices[0])
        self.assertEqual(len(set(choices[0])),3)
        self.assertEqual(choices,discovery.related_indices(archive))

    def test_transcript_can_supply_topic_signal_and_later_change_it(self):
        archive=[episode('source',transcript=[{'text':'Matterhorn bobsleds'}]),
                 episode('other','Food'),episode('match','Matterhorn bobsleds'),episode('third','Halloween')]
        self.assertEqual(discovery.related_indices(archive)[0][0],2)
        archive[0]['transcript']=[{'text':'Halloween'}]
        self.assertEqual(discovery.related_indices(archive)[0][0],3)

    def test_no_transcript_and_sparse_text_have_safe_fallback(self):
        archive=[episode(str(i)) for i in range(5)]
        self.assertEqual(discovery.related_indices(archive)[0],[1,2,3])
        self.assertEqual(discovery.related_indices(archive[:1]),[[]])
        archive[0]['description']='FastPass history and queue planning'
        archive[3]['description']='FastPass queues and park planning'
        self.assertEqual(discovery.related_indices(archive)[0][0],3)


if __name__=='__main__':unittest.main()
